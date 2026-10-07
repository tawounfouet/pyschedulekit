"""One-shot end-to-end scheduling cycle."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.application.execution_runner import ExecutionRunner, ExecutionRunResult
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.application.scheduler_engine import SchedulerEngine
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
    errors: tuple[RunPendingError, ...]

    @property
    def succeeded(self) -> int:
        return sum(result.outcome.succeeded for result in self.executions)

    @property
    def failed(self) -> int:
        return len(self.executions) - self.succeeded


class RunPendingService:
    """Coordinate scheduling, dispatch, and local execution exactly once."""

    def __init__(
        self,
        *,
        clock: Clock,
        uow_factory: UnitOfWorkFactory,
        scheduler_engine: SchedulerEngine,
        execution_service: ExecutionService,
        execution_runner: ExecutionRunner,
    ) -> None:
        self._clock = clock
        self._uow_factory = uow_factory
        self._scheduler_engine = scheduler_engine
        self._execution_service = execution_service
        self._execution_runner = execution_runner

    def run_pending(self, *, limit: int = 100) -> RunPendingResult:
        """Run one non-blocking cycle without sleeping or draining backlog."""

        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        evaluation_now = self._clock.now()
        evaluation = self._scheduler_engine.evaluate(
            evaluation_now=evaluation_now,
            limit=limit,
        )

        errors: list[RunPendingError] = []
        for request in self._list_pending_requests(limit=limit):
            try:
                self._execution_service.dispatch(
                    request_id=request.id,
                    created_at=evaluation_now,
                )
            except PersistenceConflictError:
                errors.append(
                    RunPendingError(
                        request_id=request.id,
                        code="persistence.conflict",
                        message="Execution dispatch conflicted with committed state.",
                    )
                )

        executions: list[ExecutionRunResult] = []
        for execution in self._list_queued_executions(limit=limit):
            try:
                executions.append(self._execution_runner.run(execution_id=execution.id))
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
            errors=tuple(errors),
        )

    def _list_pending_requests(self, *, limit: int) -> list[ExecutionRequest]:
        with self._uow_factory() as uow:
            return uow.requests.list_pending(limit=limit)

    def _list_queued_executions(self, *, limit: int) -> list[Execution]:
        with self._uow_factory() as uow:
            return uow.executions.list_queued(limit=limit)
