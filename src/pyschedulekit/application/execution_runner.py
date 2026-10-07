"""Application runner executing one queued Execution through an Executor port."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.application.claims import (
    ExecutionClaimCoordinator,
    ExecutionLeaseHeartbeat,
)
from pyschedulekit.application.execution_service import (
    ExecutionNotFoundError,
    ExecutionService,
)
from pyschedulekit.application.shutdown import (
    ShutdownCoordinator,
    ShutdownInProgressError,
)
from pyschedulekit.domain.claim import ClaimOwnershipError, ExecutionClaimHandle
from pyschedulekit.domain.execution import (
    AttemptId,
    Execution,
    ExecutionId,
    FailureCategory,
)
from pyschedulekit.domain.retry import RetryDecision, RetryEvaluator
from pyschedulekit.domain.time import Duration
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
        claim_coordinator: ExecutionClaimCoordinator | None = None,
        lease_heartbeat_interval: Duration | None = None,
        cancellation_controller: CancellationController | None = None,
        shutdown_coordinator: ShutdownCoordinator | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._execution_service = execution_service
        self._executor = executor
        self._clock = clock
        self._retry_evaluator = retry_evaluator or RetryEvaluator()
        self._claim_coordinator = claim_coordinator
        self._lease_heartbeat_interval = lease_heartbeat_interval
        self._cancellation_controller = cancellation_controller
        self._shutdown_coordinator = shutdown_coordinator

    def run(
        self,
        *,
        execution_id: ExecutionId,
        claim_handle: ExecutionClaimHandle | None = None,
    ) -> ExecutionRunResult:
        """Execute one logical Execution without holding a persistence transaction."""

        if self._shutdown_coordinator is not None and not self._shutdown_coordinator.try_enter(
            execution_id
        ):
            raise ShutdownInProgressError(
                "Cannot start a new Attempt while graceful shutdown is draining."
            )

        try:
            return self._run_entered(
                execution_id,
                claim_handle=claim_handle,
            )
        finally:
            if self._shutdown_coordinator is not None:
                self._shutdown_coordinator.leave(execution_id)

    def _run_entered(
        self,
        execution_id: ExecutionId,
        *,
        claim_handle: ExecutionClaimHandle | None,
    ) -> ExecutionRunResult:
        execution_snapshot = self._load_execution(execution_id)
        prepared = self._executor.prepare(execution_snapshot.target)

        attempt = self._execution_service.start_attempt(
            execution_id=execution_id,
            started_at=self._clock.now(),
            claim_handle=claim_handle,
        )

        active_claim_handle = claim_handle
        heartbeat: ExecutionLeaseHeartbeat | None = None
        if claim_handle is not None and self._claim_coordinator is not None:
            interval = self._lease_heartbeat_interval or Duration.seconds(
                self._claim_coordinator.ttl.total_seconds / 3
            )
            heartbeat = ExecutionLeaseHeartbeat(
                coordinator=self._claim_coordinator,
                clock=self._clock,
                handle=claim_handle,
                interval=interval,
            )
            heartbeat.start()

        cancellation_token = (
            self._cancellation_controller.token_for(execution_id.value)
            if self._cancellation_controller is not None
            else None
        )

        try:
            outcome = self._executor.execute(
                prepared,
                timeout=execution_snapshot.policy_snapshot.timeout,
                cancellation_token=cancellation_token,
                fencing_token=(
                    active_claim_handle.generation if active_claim_handle is not None else None
                ),
            )
            completed_at = self._clock.now()

            if heartbeat is not None:
                active_claim_handle = heartbeat.stop()
                lease_lost = heartbeat.lost
                heartbeat = None
                if lease_lost:
                    raise ClaimOwnershipError(
                        "Execution lease ownership was lost before Attempt completion."
                    )

            retry_decision: RetryDecision | None = None
            if outcome.failure is None:
                execution = self._execution_service.succeed_attempt(
                    attempt_id=attempt.id,
                    completed_at=completed_at,
                    claim_handle=active_claim_handle,
                )
            elif outcome.failure.category is FailureCategory.CANCELLED:
                execution = self._execution_service.cancel_attempt(
                    attempt_id=attempt.id,
                    completed_at=completed_at,
                    claim_handle=active_claim_handle,
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
                        claim_handle=active_claim_handle,
                    )
                else:
                    execution = self._execution_service.fail_attempt(
                        attempt_id=attempt.id,
                        failure=outcome.failure,
                        completed_at=completed_at,
                        retry_at=retry_at,
                        claim_handle=active_claim_handle,
                    )

            return ExecutionRunResult(
                execution=execution,
                attempt_id=attempt.id,
                outcome=outcome,
                retry_decision=retry_decision,
            )
        finally:
            if heartbeat is not None:
                heartbeat.stop()
            if self._cancellation_controller is not None:
                self._cancellation_controller.release(execution_id.value)

    def _load_execution(self, execution_id: ExecutionId) -> Execution:
        with self._uow_factory() as uow:
            execution = uow.executions.get(execution_id)
            if execution is None:
                raise ExecutionNotFoundError(execution_id.value)
            return execution
