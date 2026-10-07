"""Crash recovery for persisted orphaned RUNNING executions."""

from __future__ import annotations

from dataclasses import dataclass

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
from pyschedulekit.ports.persistence import PersistenceConflictError, UnitOfWorkFactory
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
        super().__init__(
            "Crash recovery did not reconcile every persisted RUNNING Execution."
        )
        self.result = result


class CrashRecoveryService:
    """Recover orphaned persisted RUNNING executions after process restart."""

    def __init__(
        self,
        *,
        clock: Clock,
        uow_factory: UnitOfWorkFactory,
        retry_evaluator: RetryEvaluator | None = None,
    ) -> None:
        self._clock = clock
        self._uow_factory = uow_factory
        self._retry_evaluator = retry_evaluator or RetryEvaluator()

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
        errors: list[CrashRecoveryError] = []

        for candidate in candidates:
            try:
                outcome = self._recover_one(
                    execution_id=candidate.id,
                    recovered_at=self._clock.now(),
                )
            except PersistenceConflictError:
                skipped.append(candidate.id)
                continue
            except CrashRecoveryConsistencyError as exc:
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

        with self._uow_factory() as uow:
            remaining = uow.executions.list_running(limit=limit)

        return CrashRecoveryResult(
            recovered_execution_ids=tuple(recovered),
            retried_execution_ids=tuple(retried),
            failed_execution_ids=tuple(failed),
            cancelled_execution_ids=tuple(cancelled),
            skipped_execution_ids=tuple(skipped),
            errors=tuple(errors),
            remaining_running_execution_ids=tuple(
                execution.id for execution in remaining
            ),
        )

    def _recover_one(
        self,
        *,
        execution_id: ExecutionId,
        recovered_at: Instant,
    ) -> str:
        with self._uow_factory() as uow:
            execution = uow.executions.get(execution_id)
            if execution is None or execution.state is not ExecutionState.RUNNING:
                return "skipped"

            active_number = execution.active_attempt_number
            if active_number is None:
                raise CrashRecoveryConsistencyError(
                    code="recovery.missing_active_attempt_number",
                    message="RUNNING Execution has no active Attempt number.",
                )

            attempt = uow.attempts.get(
                AttemptId.for_execution(execution.id, active_number)
            )
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
                uow.commit()
                return "cancelled"

            failure = Failure(
                category=FailureCategory.UNKNOWN,
                code="execution.crash_recovered",
                message="Execution attempt was orphaned by a process crash.",
                occurred_at=recovered_at,
                retryable_hint=True,
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
            uow.commit()

            return "retry" if retry_at is not None else "failed"
