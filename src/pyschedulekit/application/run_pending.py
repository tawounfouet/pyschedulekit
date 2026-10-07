"""One-shot end-to-end scheduling cycle."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.application.concurrency import AdmissionResult, ConcurrencyCoordinator
from pyschedulekit.application.execution_runner import ExecutionRunner, ExecutionRunResult
from pyschedulekit.application.scheduler_engine import SchedulerEngine
from pyschedulekit.application.shutdown import (
    ShutdownCoordinator,
    ShutdownInProgressError,
)
from pyschedulekit.domain.concurrency import ConcurrencyDecisionAction
from pyschedulekit.domain.execution import Execution
from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.schedule import ScheduleId
from pyschedulekit.domain.time import Instant
from pyschedulekit.ports.executor import ExecutorError, TargetResolutionError
from pyschedulekit.ports.persistence import PersistenceConflictError, UnitOfWorkFactory
from pyschedulekit.ports.time import Clock


@dataclass(frozen=True, slots=True)
class RunPendingError:
    """Safe per-request control-plane error reported by run_pending()."""

    request_id: RequestId
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class RunPendingResult:
    """Structured result of one non-blocking scheduling cycle."""

    evaluation_now: Instant
    materialized_request_ids: tuple[RequestId, ...]
    executions: tuple[ExecutionRunResult, ...]
    schedule_conflicts: tuple[ScheduleId, ...]
    unsupported_policy_schedules: tuple[ScheduleId, ...]
    recovery_limit_schedules: tuple[ScheduleId, ...]
    admissions: tuple[AdmissionResult, ...]
    errors: tuple[RunPendingError, ...]

    @property
    def succeeded(self) -> int:
        return sum(result.outcome.succeeded for result in self.executions)

    @property
    def failed(self) -> int:
        return sum(
            result.execution.is_terminal and not result.outcome.succeeded
            for result in self.executions
        )

    @property
    def retry_scheduled(self) -> int:
        return sum(not result.execution.is_terminal for result in self.executions)

    @property
    def queued_request_ids(self) -> tuple[RequestId, ...]:
        return tuple(
            admission.request_id
            for admission in self.admissions
            if admission.action is ConcurrencyDecisionAction.QUEUE
        )

    @property
    def dropped_request_ids(self) -> tuple[RequestId, ...]:
        return tuple(
            admission.request_id
            for admission in self.admissions
            if admission.action is ConcurrencyDecisionAction.DROP
        )


class RunPendingService:
    """Coordinate scheduling, dispatch, and local execution exactly once."""

    def __init__(
        self,
        *,
        clock: Clock,
        uow_factory: UnitOfWorkFactory,
        scheduler_engine: SchedulerEngine,
        concurrency_coordinator: ConcurrencyCoordinator,
        execution_runner: ExecutionRunner,
        shutdown_coordinator: ShutdownCoordinator | None = None,
    ) -> None:
        self._clock = clock
        self._uow_factory = uow_factory
        self._scheduler_engine = scheduler_engine
        self._concurrency_coordinator = concurrency_coordinator
        self._execution_runner = execution_runner
        self._shutdown_coordinator = shutdown_coordinator

    def run_pending(self, *, limit: int = 100) -> RunPendingResult:
        """Run one non-blocking cycle without sleeping or draining backlog."""

        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        evaluation_now = self._clock.now()
        if self._shutdown_requested():
            return RunPendingResult(
                evaluation_now=evaluation_now,
                materialized_request_ids=(),
                executions=(),
                schedule_conflicts=(),
                unsupported_policy_schedules=(),
                recovery_limit_schedules=(),
                admissions=(),
                errors=(),
            )

        evaluation = self._scheduler_engine.evaluate(
            evaluation_now=evaluation_now,
            limit=limit,
        )

        errors: list[RunPendingError] = []
        admissions: list[AdmissionResult] = []
        for request in self._list_admission_candidates(limit=limit):
            if self._shutdown_requested():
                break
            try:
                admissions.append(
                    self._concurrency_coordinator.admit(
                        request_id=request.id,
                        created_at=evaluation_now,
                    )
                )
            except PersistenceConflictError:
                errors.append(
                    RunPendingError(
                        request_id=request.id,
                        code="persistence.conflict",
                        message="Execution admission conflicted with committed state.",
                    )
                )

        executions: list[ExecutionRunResult] = []
        for execution in self._list_runnable_executions(now=evaluation_now, limit=limit):
            if self._shutdown_requested():
                break
            try:
                executions.append(self._execution_runner.run(execution_id=execution.id))
            except ShutdownInProgressError:
                break
            except TargetResolutionError:
                errors.append(
                    RunPendingError(
                        request_id=execution.request_id,
                        code="executor.target_resolution",
                        message="Execution target could not be resolved.",
                    )
                )
            except ExecutorError:
                errors.append(
                    RunPendingError(
                        request_id=execution.request_id,
                        code="executor.error",
                        message="Executor control-plane operation failed.",
                    )
                )
            except PersistenceConflictError:
                errors.append(
                    RunPendingError(
                        request_id=execution.request_id,
                        code="persistence.conflict",
                        message="Execution lifecycle update conflicted with committed state.",
                    )
                )

        return RunPendingResult(
            evaluation_now=evaluation_now,
            materialized_request_ids=tuple(request.id for request in evaluation.requests),
            executions=tuple(executions),
            schedule_conflicts=evaluation.conflicts,
            unsupported_policy_schedules=evaluation.unsupported_policy_schedules,
            recovery_limit_schedules=evaluation.recovery_limit_schedules,
            admissions=tuple(admissions),
            errors=tuple(errors),
        )

    def _shutdown_requested(self) -> bool:
        return (
            self._shutdown_coordinator is not None
            and self._shutdown_coordinator.is_requested
        )

    def _list_admission_candidates(self, *, limit: int) -> list[ExecutionRequest]:
        with self._uow_factory() as uow:
            return uow.requests.list_admission_candidates(limit=limit)

    def _list_runnable_executions(
        self,
        *,
        now: Instant,
        limit: int,
    ) -> list[Execution]:
        with self._uow_factory() as uow:
            return uow.executions.list_runnable(now=now, limit=limit)
