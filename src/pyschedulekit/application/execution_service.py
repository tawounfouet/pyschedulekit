"""Application service coordinating ExecutionRequest, Execution, and Attempt lifecycles."""

from __future__ import annotations

from pyschedulekit.domain.execution import (
    Attempt,
    AttemptId,
    Execution,
    ExecutionId,
    ExecutionPolicySnapshot,
    Failure,
)
from pyschedulekit.domain.execution_request import (
    ExecutionRequestState,
    InvalidExecutionRequestTransitionError,
    RequestId,
)
from pyschedulekit.domain.time import Instant
from pyschedulekit.ports.persistence import UnitOfWork, UnitOfWorkFactory


class ExecutionRequestNotFoundError(LookupError):
    """Raised when an ExecutionRequest cannot be found."""


class ExecutionNotFoundError(LookupError):
    """Raised when an Execution cannot be found."""


class AttemptNotFoundError(LookupError):
    """Raised when an Attempt cannot be found."""


class ExecutionConsistencyError(RuntimeError):
    """Raised when persisted execution state violates expected invariants."""


class ExecutionService:
    """Application service coordinating execution lifecycle transitions."""

    def __init__(self, *, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def dispatch(
        self,
        *,
        request_id: RequestId,
        created_at: Instant,
        policy_snapshot: ExecutionPolicySnapshot | None = None,
    ) -> Execution:
        """Atomically turn one dispatchable request into one queued Execution."""

        with self._uow_factory() as uow:
            request = uow.requests.get(request_id)
            if request is None:
                raise ExecutionRequestNotFoundError(request_id.value)

            existing = uow.executions.get_by_request(request.id)

            if request.state is ExecutionRequestState.DISPATCHED:
                if existing is None:
                    raise ExecutionConsistencyError(
                        "Dispatched ExecutionRequest has no persisted Execution."
                    )
                return existing

            if request.state is ExecutionRequestState.CANCELLED:
                raise InvalidExecutionRequestTransitionError(
                    "Cancelled ExecutionRequest cannot be dispatched."
                )

            if existing is not None:
                request.mark_dispatched()
                uow.requests.save(request)
                uow.commit()
                return existing

            request.mark_dispatched()
            execution = Execution.from_request(
                request=request,
                created_at=created_at,
                policy_snapshot=policy_snapshot,
            )

            uow.requests.save(request)
            uow.executions.add(execution)
            uow.commit()
            return execution

    def start_attempt(
        self,
        *,
        execution_id: ExecutionId,
        started_at: Instant,
    ) -> Attempt:
        """Atomically start exactly one new Attempt for an Execution."""

        with self._uow_factory() as uow:
            execution = uow.executions.get(execution_id)
            if execution is None:
                raise ExecutionNotFoundError(execution_id.value)

            attempt = execution.start_attempt(started_at=started_at)
            uow.executions.save(execution)
            uow.attempts.add(attempt)
            uow.commit()
            return attempt

    def succeed_attempt(
        self,
        *,
        attempt_id: AttemptId,
        completed_at: Instant,
    ) -> Execution:
        """Persist a successful Attempt and terminal successful Execution."""

        with self._uow_factory() as uow:
            attempt, execution = self._load_attempt_and_execution(uow, attempt_id)
            attempt.succeed(completed_at=completed_at)
            execution.finish_attempt(attempt=attempt)

            uow.attempts.save(attempt)
            uow.executions.save(execution)
            uow.commit()
            return execution

    def fail_attempt(
        self,
        *,
        attempt_id: AttemptId,
        failure: Failure,
        completed_at: Instant,
        retry_at: Instant | None = None,
    ) -> Execution:
        """Persist a failed Attempt and either fail or park the Execution for retry."""

        with self._uow_factory() as uow:
            attempt, execution = self._load_attempt_and_execution(uow, attempt_id)
            attempt.fail(failure=failure, completed_at=completed_at)
            execution.finish_attempt(attempt=attempt, retry_at=retry_at)

            uow.attempts.save(attempt)
            uow.executions.save(execution)
            uow.commit()
            return execution

    def timeout_attempt(
        self,
        *,
        attempt_id: AttemptId,
        completed_at: Instant,
        retry_at: Instant | None = None,
    ) -> Execution:
        """Persist a timed-out Attempt and update its Execution."""

        with self._uow_factory() as uow:
            attempt, execution = self._load_attempt_and_execution(uow, attempt_id)
            attempt.timeout(completed_at=completed_at)
            execution.finish_attempt(attempt=attempt, retry_at=retry_at)

            uow.attempts.save(attempt)
            uow.executions.save(execution)
            uow.commit()
            return execution

    def cancel_attempt(
        self,
        *,
        attempt_id: AttemptId,
        completed_at: Instant,
    ) -> Execution:
        """Persist cancellation of a running Attempt and its Execution."""

        with self._uow_factory() as uow:
            attempt, execution = self._load_attempt_and_execution(uow, attempt_id)
            attempt.cancel(completed_at=completed_at)
            execution.finish_attempt(attempt=attempt)

            uow.attempts.save(attempt)
            uow.executions.save(execution)
            uow.commit()
            return execution

    def cancel_execution(
        self,
        *,
        execution_id: ExecutionId,
        completed_at: Instant,
    ) -> Execution:
        """Cancel a queued or retry-waiting Execution."""

        with self._uow_factory() as uow:
            execution = uow.executions.get(execution_id)
            if execution is None:
                raise ExecutionNotFoundError(execution_id.value)

            execution.cancel(completed_at=completed_at)
            uow.executions.save(execution)
            uow.commit()
            return execution

    @staticmethod
    def _load_attempt_and_execution(
        uow: UnitOfWork,
        attempt_id: AttemptId,
    ) -> tuple[Attempt, Execution]:
        attempt = uow.attempts.get(attempt_id)
        if attempt is None:
            raise AttemptNotFoundError(attempt_id.value)

        execution = uow.executions.get(attempt.execution_id)
        if execution is None:
            raise ExecutionConsistencyError(
                "Attempt references an Execution that does not exist."
            )

        return attempt, execution
