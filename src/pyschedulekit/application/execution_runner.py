"""Application runner executing one queued Execution through an Executor port."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.application.execution_service import (
    ExecutionNotFoundError,
    ExecutionService,
)
from pyschedulekit.domain.execution import AttemptId, Execution, ExecutionId
from pyschedulekit.ports.executor import Executor, ExecutorOutcome
from pyschedulekit.ports.persistence import UnitOfWorkFactory
from pyschedulekit.ports.time import Clock


@dataclass(frozen=True, slots=True)
class ExecutionRunResult:
    """Result of one local Execution run attempt."""

    execution: Execution
    attempt_id: AttemptId
    outcome: ExecutorOutcome


class ExecutionRunner:
    """Coordinates resolution, Attempt lifecycle, and side-effect execution."""

    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        execution_service: ExecutionService,
        executor: Executor,
        clock: Clock,
    ) -> None:
        self._uow_factory = uow_factory
        self._execution_service = execution_service
        self._executor = executor
        self._clock = clock

    def run(self, *, execution_id: ExecutionId) -> ExecutionRunResult:
        """Execute one logical Execution without holding a persistence transaction."""

        target = self._load_target(execution_id)
        prepared = self._executor.prepare(target)

        attempt = self._execution_service.start_attempt(
            execution_id=execution_id,
            started_at=self._clock.now(),
        )

        outcome = self._executor.execute(prepared)
        completed_at = self._clock.now()

        if outcome.failure is None:
            execution = self._execution_service.succeed_attempt(
                attempt_id=attempt.id,
                completed_at=completed_at,
            )
        else:
            execution = self._execution_service.fail_attempt(
                attempt_id=attempt.id,
                failure=outcome.failure,
                completed_at=completed_at,
            )

        return ExecutionRunResult(
            execution=execution,
            attempt_id=attempt.id,
            outcome=outcome,
        )

    def _load_target(self, execution_id: ExecutionId):
        with self._uow_factory() as uow:
            execution = uow.executions.get(execution_id)
            if execution is None:
                raise ExecutionNotFoundError(execution_id.value)
            return execution.target
