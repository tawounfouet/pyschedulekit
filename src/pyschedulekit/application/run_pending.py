"""One-shot end-to-end scheduling cycle."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.application.claims import ExecutionClaimCoordinator
from pyschedulekit.application.concurrency import AdmissionResult, ConcurrencyCoordinator
from pyschedulekit.application.execution_runner import ExecutionRunner, ExecutionRunResult
from pyschedulekit.application.observability import Observer
from pyschedulekit.application.recovery import (
    CrashRecoveryIncompleteError,
    CrashRecoveryService,
)
from pyschedulekit.application.scheduler_engine import SchedulerEngine
from pyschedulekit.application.shutdown import (
    ShutdownCoordinator,
    ShutdownInProgressError,
)
from pyschedulekit.domain.claim import ClaimOwnershipError, ExecutionClaimHandle
from pyschedulekit.domain.concurrency import ConcurrencyDecisionAction
from pyschedulekit.domain.execution import (
    Execution,
    ExecutionId,
    InvalidExecutionTransitionError,
)
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
    claim_denied_execution_ids: tuple[ExecutionId, ...] = ()
    materialization_denied_schedule_ids: tuple[ScheduleId, ...] = ()

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
            if admission.action is ConcurrencyDecisionAction.QUEUE and not admission.lock_denied
        )

    @property
    def admission_lock_denied_request_ids(self) -> tuple[RequestId, ...]:
        return tuple(admission.request_id for admission in self.admissions if admission.lock_denied)

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
        claim_coordinator: ExecutionClaimCoordinator | None = None,
        distributed_recovery_service: CrashRecoveryService | None = None,
        shutdown_coordinator: ShutdownCoordinator | None = None,
        observer: Observer | None = None,
    ) -> None:
        self._clock = clock
        self._uow_factory = uow_factory
        self._scheduler_engine = scheduler_engine
        self._concurrency_coordinator = concurrency_coordinator
        self._execution_runner = execution_runner
        self._claim_coordinator = claim_coordinator
        self._distributed_recovery_service = distributed_recovery_service
        self._shutdown_coordinator = shutdown_coordinator
        self._observer = observer or Observer()

    def run_pending(self, *, limit: int = 100) -> RunPendingResult:
        """Run one non-blocking cycle without sleeping or draining backlog."""

        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        if self._shutdown_requested():
            evaluation_now = self._clock.now()
            result = RunPendingResult(
                evaluation_now=evaluation_now,
                materialized_request_ids=(),
                executions=(),
                schedule_conflicts=(),
                unsupported_policy_schedules=(),
                recovery_limit_schedules=(),
                admissions=(),
                errors=(),
            )
            self._record_cycle(result, shutdown_requested=True)
            return result

        if self._distributed_recovery_service is not None:
            recovery = self._distributed_recovery_service.recover(limit=limit)
            if not recovery.complete:
                raise CrashRecoveryIncompleteError(recovery)

        evaluation_now = self._clock.now()
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
        claim_denied: list[ExecutionId] = []
        for execution in self._list_runnable_executions(now=evaluation_now, limit=limit):
            if self._shutdown_requested():
                break

            claim_handle: ExecutionClaimHandle | None = None
            if self._claim_coordinator is not None:
                acquisition = self._claim_coordinator.acquire(
                    execution_id=execution.id,
                    now=self._clock.now(),
                )
                if not acquisition.acquired or acquisition.handle is None:
                    claim_denied.append(execution.id)
                    continue
                claim_handle = acquisition.handle

            try:
                executions.append(
                    self._execution_runner.run(
                        execution_id=execution.id,
                        claim_handle=claim_handle,
                    )
                )
            except InvalidExecutionTransitionError:
                self._release_unstarted_claim(claim_handle)
                errors.append(
                    RunPendingError(
                        request_id=execution.request_id,
                        code="execution.transition",
                        message="Execution state changed concurrently; skipped this cycle.",
                    )
                )
            except ClaimOwnershipError:
                claim_denied.append(execution.id)
            except ShutdownInProgressError:
                self._release_unstarted_claim(claim_handle)
                break
            except TargetResolutionError:
                self._release_unstarted_claim(claim_handle)
                errors.append(
                    RunPendingError(
                        request_id=execution.request_id,
                        code="executor.target_resolution",
                        message="Execution target could not be resolved.",
                    )
                )
            except ExecutorError:
                self._release_unstarted_claim(claim_handle)
                errors.append(
                    RunPendingError(
                        request_id=execution.request_id,
                        code="executor.error",
                        message="Executor control-plane operation failed.",
                    )
                )
            except PersistenceConflictError:
                self._release_unstarted_claim(claim_handle)
                errors.append(
                    RunPendingError(
                        request_id=execution.request_id,
                        code="persistence.conflict",
                        message="Execution lifecycle update conflicted with committed state.",
                    )
                )
        result = RunPendingResult(
            evaluation_now=evaluation_now,
            materialized_request_ids=tuple(request.id for request in evaluation.requests),
            executions=tuple(executions),
            schedule_conflicts=evaluation.conflicts,
            unsupported_policy_schedules=evaluation.unsupported_policy_schedules,
            recovery_limit_schedules=evaluation.recovery_limit_schedules,
            admissions=tuple(admissions),
            errors=tuple(errors),
            claim_denied_execution_ids=tuple(claim_denied),
            materialization_denied_schedule_ids=evaluation.coordination_denied_schedules,
        )
        self._record_cycle(result)
        return result

    def _record_cycle(
        self,
        result: RunPendingResult,
        *,
        shutdown_requested: bool = False,
    ) -> None:
        self._observer.record(
            name="scheduler.cycle.completed",
            recorded_at=result.evaluation_now,
            materialized_requests=len(result.materialized_request_ids),
            executions=len(result.executions),
            succeeded=result.succeeded,
            failed=result.failed,
            retry_scheduled=result.retry_scheduled,
            schedule_conflicts=len(result.schedule_conflicts),
            recovery_limit_schedules=len(result.recovery_limit_schedules),
            admissions=len(result.admissions),
            queued=len(result.queued_request_ids),
            dropped=len(result.dropped_request_ids),
            admission_lock_denied=len(result.admission_lock_denied_request_ids),
            claim_denied=len(result.claim_denied_execution_ids),
            materialization_denied=len(result.materialization_denied_schedule_ids),
            errors=len(result.errors),
            shutdown_requested=shutdown_requested,
        )

    def _release_unstarted_claim(
        self,
        handle: ExecutionClaimHandle | None,
    ) -> None:
        if self._claim_coordinator is None or handle is None:
            return
        self._claim_coordinator.release(
            handle=handle,
            released_at=self._clock.now(),
        )

    def _shutdown_requested(self) -> bool:
        return self._shutdown_coordinator is not None and self._shutdown_coordinator.is_requested

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
