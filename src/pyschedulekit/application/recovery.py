"""Crash recovery for persisted orphaned RUNNING executions."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.application.claims import ExecutionClaimCoordinator
from pyschedulekit.application.outbox import make_outbox_message
from pyschedulekit.domain.claim import ClaimOwnershipError, ExecutionClaimHandle
from pyschedulekit.domain.execution import (
    AttemptId,
    AttemptState,
    ExecutionId,
    ExecutionState,
    Failure,
    FailureCategory,
)
from pyschedulekit.domain.retry import RetryEvaluator
from pyschedulekit.domain.time import Instant
from pyschedulekit.ports.persistence import PersistenceConflictError, UnitOfWork, UnitOfWorkFactory
from pyschedulekit.ports.time import Clock


@dataclass(frozen=True, slots=True)
class CrashRecoveryError:
    """One persisted inconsistency encountered during crash recovery."""

    execution_id: ExecutionId
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class CrashRecoveryResult:
    """Structured result of one crash-recovery pass."""

    recovered_execution_ids: tuple[ExecutionId, ...]
    retried_execution_ids: tuple[ExecutionId, ...]
    failed_execution_ids: tuple[ExecutionId, ...]
    cancelled_execution_ids: tuple[ExecutionId, ...]
    skipped_execution_ids: tuple[ExecutionId, ...]
    errors: tuple[CrashRecoveryError, ...]
    remaining_running_execution_ids: tuple[ExecutionId, ...]
    protected_execution_ids: tuple[ExecutionId, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.remaining_running_execution_ids and not self.errors

    @property
    def recovered(self) -> int:
        return len(self.recovered_execution_ids)

    @property
    def failed(self) -> int:
        return len(self.failed_execution_ids)

    @property
    def retried(self) -> int:
        return len(self.retried_execution_ids)

    @property
    def cancelled(self) -> int:
        return len(self.cancelled_execution_ids)


class CrashRecoveryConsistencyError(RuntimeError):
    """Raised when persisted RUNNING state cannot be reconciled safely."""

    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class CrashRecoveryActiveRuntimeError(RuntimeError):
    """Raised when manual crash recovery is requested while local work is active."""


class CrashRecoveryIncompleteError(RuntimeError):
    """Raised when persisted RUNNING state remains after a recovery pass."""

    def __init__(self, result: CrashRecoveryResult) -> None:
        super().__init__("Crash recovery did not reconcile every unprotected RUNNING Execution.")
        self.result = result


class CrashRecoveryService:
    """Recover orphaned RUNNING work while respecting active distributed leases."""

    def __init__(
        self,
        *,
        clock: Clock,
        uow_factory: UnitOfWorkFactory,
        retry_evaluator: RetryEvaluator | None = None,
        claim_coordinator: ExecutionClaimCoordinator | None = None,
    ) -> None:
        self._clock = clock
        self._uow_factory = uow_factory
        self._retry_evaluator = retry_evaluator or RetryEvaluator()
        self._claim_coordinator = claim_coordinator

    def recover(self, *, limit: int = 1000) -> CrashRecoveryResult:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        with self._uow_factory() as uow:
            candidates = uow.executions.list_running(limit=limit)

        recovered: list[ExecutionId] = []
        retried: list[ExecutionId] = []
        failed: list[ExecutionId] = []
        cancelled: list[ExecutionId] = []
        skipped: list[ExecutionId] = []
        protected: list[ExecutionId] = []
        errors: list[CrashRecoveryError] = []

        for candidate in candidates:
            recovered_at = self._clock.now()
            lease_handle: ExecutionClaimHandle | None = None

            if self._claim_coordinator is not None:
                acquisition = self._claim_coordinator.acquire_for_recovery(
                    execution_id=candidate.id,
                    now=recovered_at,
                )
                if not acquisition.acquired or acquisition.handle is None:
                    if acquisition.reason == "already_claimed":
                        protected.append(candidate.id)
                    else:
                        skipped.append(candidate.id)
                    continue
                lease_handle = acquisition.handle

            try:
                outcome = self._recover_one(
                    execution_id=candidate.id,
                    recovered_at=recovered_at,
                    lease_handle=lease_handle,
                )
            except (PersistenceConflictError, ClaimOwnershipError):
                self._release_acquired_handle_best_effort(
                    handle=lease_handle,
                    released_at=recovered_at,
                )
                skipped.append(candidate.id)
                continue
            except CrashRecoveryConsistencyError as exc:
                self._release_acquired_handle_best_effort(
                    handle=lease_handle,
                    released_at=recovered_at,
                )
                errors.append(
                    CrashRecoveryError(
                        execution_id=candidate.id,
                        code=exc.code,
                        message=str(exc),
                    )
                )
                continue

            if outcome == "skipped":
                skipped.append(candidate.id)
            elif outcome == "retry":
                recovered.append(candidate.id)
                retried.append(candidate.id)
            elif outcome == "failed":
                recovered.append(candidate.id)
                failed.append(candidate.id)
            elif outcome == "cancelled":
                recovered.append(candidate.id)
                cancelled.append(candidate.id)
            else:
                errors.append(
                    CrashRecoveryError(
                        execution_id=candidate.id,
                        code="recovery.unknown_outcome",
                        message=f"Unexpected recovery outcome {outcome!r}.",
                    )
                )

        remaining, active_protected = self._remaining_unprotected(limit=limit)
        for execution_id in active_protected:
            if execution_id not in protected:
                protected.append(execution_id)

        return CrashRecoveryResult(
            recovered_execution_ids=tuple(recovered),
            retried_execution_ids=tuple(retried),
            failed_execution_ids=tuple(failed),
            cancelled_execution_ids=tuple(cancelled),
            skipped_execution_ids=tuple(skipped),
            errors=tuple(errors),
            remaining_running_execution_ids=tuple(remaining),
            protected_execution_ids=tuple(protected),
        )

    def _recover_one(
        self,
        *,
        execution_id: ExecutionId,
        recovered_at: Instant,
        lease_handle: ExecutionClaimHandle | None,
    ) -> str:
        with self._uow_factory() as uow:
            execution = uow.executions.get(execution_id)
            if execution is None or execution.state is not ExecutionState.RUNNING:
                self._release_lease_if_present(
                    uow=uow,
                    handle=lease_handle,
                    released_at=recovered_at,
                )
                if lease_handle is not None:
                    uow.commit()
                return "skipped"

            self._release_lease_if_present(
                uow=uow,
                handle=lease_handle,
                released_at=recovered_at,
            )

            active_number = execution.active_attempt_number
            if active_number is None:
                raise CrashRecoveryConsistencyError(
                    code="recovery.missing_active_attempt_number",
                    message="RUNNING Execution has no active Attempt number.",
                )

            attempt = uow.attempts.get(AttemptId.for_execution(execution.id, active_number))
            if attempt is None:
                raise CrashRecoveryConsistencyError(
                    code="recovery.missing_attempt",
                    message="RUNNING Execution references an Attempt that does not exist.",
                )
            if attempt.state is not AttemptState.RUNNING:
                raise CrashRecoveryConsistencyError(
                    code="recovery.attempt_not_running",
                    message="RUNNING Execution references a non-RUNNING Attempt.",
                )

            if execution.cancellation_requested:
                attempt.cancel(completed_at=recovered_at)
                execution.finish_attempt(attempt=attempt)
                uow.attempts.save(attempt)
                uow.executions.save(execution)
                self._add_recovery_outbox(
                    uow=uow,
                    attempt_id=attempt.id,
                    attempt_number=attempt.number,
                    attempt_state=attempt.state.value,
                    execution_id=execution.id,
                    execution_state=execution.state.value,
                    recovered_at=recovered_at,
                )
                uow.commit()
                return "cancelled"

            failure = Failure(
                category=FailureCategory.UNKNOWN,
                code="execution.crash_recovered",
                message="Execution attempt was orphaned by a process crash.",
                occurred_at=recovered_at,
                retryable_hint=None,
                details=(("recovery", "crash"),),
            )
            attempt.fail(
                failure=failure,
                completed_at=recovered_at,
            )
            decision = self._retry_evaluator.evaluate(
                policy=execution.policy_snapshot.retry,
                attempt_number=attempt.number,
                failure=failure,
            )
            retry_at = (
                recovered_at.add(decision.delay)
                if decision.should_retry and decision.delay is not None
                else None
            )
            execution.finish_attempt(
                attempt=attempt,
                retry_at=retry_at,
            )

            uow.attempts.save(attempt)
            uow.executions.save(execution)
            self._add_recovery_outbox(
                uow=uow,
                attempt_id=attempt.id,
                attempt_number=attempt.number,
                attempt_state=attempt.state.value,
                execution_id=execution.id,
                execution_state=execution.state.value,
                recovered_at=recovered_at,
            )
            uow.commit()

            return "retry" if retry_at is not None else "failed"

    def _remaining_unprotected(
        self,
        *,
        limit: int,
    ) -> tuple[list[ExecutionId], list[ExecutionId]]:
        with self._uow_factory() as uow:
            running = uow.executions.list_running(limit=limit)
            if self._claim_coordinator is None:
                return [execution.id for execution in running], []

            now = self._clock.now()
            remaining: list[ExecutionId] = []
            protected: list[ExecutionId] = []
            for execution in running:
                claim = uow.claims.get(execution.id)
                if claim is not None and claim.is_active(now=now):
                    protected.append(execution.id)
                else:
                    remaining.append(execution.id)
            return remaining, protected

    def _release_acquired_handle_best_effort(
        self,
        *,
        handle: ExecutionClaimHandle | None,
        released_at: Instant,
    ) -> None:
        if handle is None or self._claim_coordinator is None:
            return
        self._claim_coordinator.release(
            handle=handle,
            released_at=released_at,
        )

    @staticmethod
    def _release_lease_if_present(
        *,
        uow: UnitOfWork,
        handle: ExecutionClaimHandle | None,
        released_at: Instant,
    ) -> None:
        if handle is None:
            return
        claim = uow.claims.get(handle.execution_id)
        if claim is None:
            raise ClaimOwnershipError("Recovery lease disappeared before reconciliation.")
        claim.release(
            worker_id=handle.worker_id,
            token=handle.token,
            generation=handle.generation,
            released_at=released_at,
        )
        uow.claims.save(claim)

    @staticmethod
    def _add_recovery_outbox(
        *,
        uow: UnitOfWork,
        attempt_id: AttemptId,
        attempt_number: int,
        attempt_state: str,
        execution_id: ExecutionId,
        execution_state: str,
        recovered_at: Instant,
    ) -> None:
        uow.outbox.add(
            make_outbox_message(
                event_type="execution.attempt.completed",
                aggregate_type="attempt",
                aggregate_id=attempt_id.value,
                created_at=recovered_at,
                payload={
                    "attempt_id": attempt_id.value,
                    "attempt_number": str(attempt_number),
                    "attempt_state": attempt_state,
                    "execution_id": execution_id.value,
                    "execution_state": execution_state,
                    "recovery": "crash",
                },
                sequence=1,
            )
        )
