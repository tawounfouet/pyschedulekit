"""One-shot end-to-end scheduling cycle."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.application.execution_runner import ExecutionRunResult, ExecutionRunner
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.application.scheduler_engine import SchedulerEngine
from pyschedulekit.domain.execution import ExecutionId, ExecutionState
from pyschedulekit.domain.execution_request import RequestId
from pyschedulekit.domain.schedule import ScheduleId
from pyschedulekit.domain.time import Instant
from pyschedulekit.ports.executor import ExecutorError, TargetResolutionError
from pyschedulekit.ports.persistence import PersistenceConflictError
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
    skipped_execution_ids: tuple[ExecutionId, ...]
    schedule_conflicts: tuple[ScheduleId, ...]
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
        scheduler_engine: SchedulerEngine,
        execution_service: ExecutionService,
        execution_runner: ExecutionRunner,
    ) -> None:
        self._clock = clock
        self._scheduler_engine = scheduler_engine
        self._execution_service = execution_service
        self._execution_runner = execution_runner

    def run_pending(self, *, limit: int = 100) -> RunPendingResult:
        """Run one non-blocking cycle without sleeping or draining backlog."""

        evaluation_now = self._clock.now()
        evaluation = self._scheduler_engine.evaluate(
            evaluation_now=evaluation_now,
            limit=limit,
        )

        executions: list[ExecutionRunResult] = []
        skipped: list[ExecutionId] = []
        errors: list[RunPendingError] = []

        for request in evaluation.requests:
            try:
                execution = self._execution_service.dispatch(
                    request_id=request.id,
                    created_at=evaluation_now,
                )

                if execution.state is not ExecutionState.QUEUED:
                    skipped.append(execution.id)
                    continue

                executions.append(
                    self._execution_runner.run(execution_id=execution.id)
                )
            except TargetResolutionError:
                errors.append(
                    RunPendingError(
                        request_id=request.id,
                        code="executor.target_resolution",
                        message="Execution target could not be resolved.",
                    )
                )
            except ExecutorError:
                errors.append(
                    RunPendingError(
                        request_id=request.id,
                        code="executor.error",
                        message="Executor control-plane operation failed.",
                    )
                )
            except PersistenceConflictError:
                errors.append(
                    RunPendingError(
                        request_id=request.id,
                        code="persistence.conflict",
                        message="Execution lifecycle update conflicted with committed state.",
                    )
                )

        return RunPendingResult(
            evaluation_now=evaluation_now,
            materialized_request_ids=tuple(request.id for request in evaluation.requests),
            executions=tuple(executions),
            skipped_execution_ids=tuple(skipped),
            schedule_conflicts=evaluation.conflicts,
            errors=tuple(errors),
        )
