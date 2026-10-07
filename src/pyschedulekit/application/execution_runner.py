"""Application runner executing one queued Execution through an Executor port."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.application.execution_service import (
    ExecutionNotFoundError,
    ExecutionService,
)
from pyschedulekit.domain.execution import (
    AttemptId,
    Execution,
    ExecutionId,
    FailureCategory,
)
from pyschedulekit.domain.retry import RetryDecision, RetryEvaluator
from pyschedulekit.ports.cancellation import CancellationController
from pyschedulekit.ports.executor import Executor, ExecutorOutcome
from pyschedulekit.ports.persistence import UnitOfWorkFactory
from pyschedulekit.ports.time import Clock


@dataclass(frozen=True, slots=True)
class ExecutionRunResult:
    """Result of one local Execution run attempt."""

    execution: Execution
    attempt_id: AttemptId
    outcome: ExecutorOutcome
    retry_decision: RetryDecision | None = None


class ExecutionRunner:
    """Coordinates resolution, Attempt lifecycle, and side-effect execution."""

    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        execution_service: ExecutionService,
        executor: Executor,
        clock: Clock,
        retry_evaluator: RetryEvaluator | None = None,
        cancellation_controller: CancellationController | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._execution_service = execution_service
        self._executor = executor
        self._clock = clock
        self._retry_evaluator = retry_evaluator or RetryEvaluator()
        self._cancellation_controller = cancellation_controller

    def run(self, *, execution_id: ExecutionId) -> ExecutionRunResult:
        """Execute one logical Execution without holding a persistence transaction."""

        execution_snapshot = self._load_execution(execution_id)
        prepared = self._executor.prepare(execution_snapshot.target)

        attempt = self._execution_service.start_attempt(
            execution_id=execution_id,
            started_at=self._clock.now(),
        )

        cancellation_token = (
            self._cancellation_controller.token_for(execution_id.value)
            if self._cancellation_controller is not None
            else None
        )
        outcome = self._executor.execute(
            prepared,
            timeout=execution_snapshot.policy_snapshot.timeout,
            cancellation_token=cancellation_token,
        )
        completed_at = self._clock.now()

        retry_decision: RetryDecision | None = None
        if outcome.failure is None:
            execution = self._execution_service.succeed_attempt(
                attempt_id=attempt.id,
                completed_at=completed_at,
            )
        elif outcome.failure.category is FailureCategory.CANCELLED:
            execution = self._execution_service.cancel_attempt(
                attempt_id=attempt.id,
                completed_at=completed_at,
            )
        else:
            retry_decision = self._retry_evaluator.evaluate(
                policy=execution_snapshot.policy_snapshot.retry,
                attempt_number=attempt.number,
                failure=outcome.failure,
            )
            retry_at = (
                completed_at.add(retry_decision.delay)
                if retry_decision.should_retry and retry_decision.delay is not None
                else None
            )
            if outcome.failure.category is FailureCategory.TIMEOUT:
                execution = self._execution_service.timeout_attempt(
                    attempt_id=attempt.id,
                    completed_at=completed_at,
                    retry_at=retry_at,
                )
            else:
                execution = self._execution_service.fail_attempt(
                    attempt_id=attempt.id,
                    failure=outcome.failure,
                    completed_at=completed_at,
                    retry_at=retry_at,
                )

        if self._cancellation_controller is not None:
            self._cancellation_controller.release(execution_id.value)

        return ExecutionRunResult(
            execution=execution,
            attempt_id=attempt.id,
            outcome=outcome,
            retry_decision=retry_decision,
        )

    def _load_execution(self, execution_id: ExecutionId) -> Execution:
        with self._uow_factory() as uow:
            execution = uow.executions.get(execution_id)
            if execution is None:
                raise ExecutionNotFoundError(execution_id.value)
            return execution
