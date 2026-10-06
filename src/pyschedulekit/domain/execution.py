"""Execution and Attempt domain state machines."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from pyschedulekit.domain.execution_request import (
    ExecutionRequest,
    ExecutionRequestState,
    RequestId,
)
from pyschedulekit.domain.schedule import TargetRef
from pyschedulekit.domain.time import Duration, Instant


class InvalidExecutionTransitionError(ValueError):
    """Raised when an Execution transition is invalid."""


class InvalidAttemptTransitionError(ValueError):
    """Raised when an Attempt transition is invalid."""


@dataclass(frozen=True, slots=True)
class ExecutionId:
    """Stable identity of one Execution."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("ExecutionId must not be empty.")

    @classmethod
    def for_request(cls, request_id: RequestId) -> ExecutionId:
        canonical = f"execution|{request_id.value}"
        return cls(sha256(canonical.encode("utf-8")).hexdigest())


@dataclass(frozen=True, slots=True)
class AttemptId:
    """Stable identity of one numbered Attempt."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("AttemptId must not be empty.")

    @classmethod
    def for_execution(cls, execution_id: ExecutionId, attempt_number: int) -> AttemptId:
        if attempt_number < 1:
            raise ValueError("attempt_number must be greater than or equal to 1.")
        canonical = f"attempt|{execution_id.value}|{attempt_number}"
        return cls(sha256(canonical.encode("utf-8")).hexdigest())


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    """Logical key preserved across every Attempt of one Execution."""

    value: str

    @classmethod
    def for_request(cls, request_id: RequestId) -> IdempotencyKey:
        canonical = f"idempotency|{request_id.value}"
        return cls(sha256(canonical.encode("utf-8")).hexdigest())


@dataclass(frozen=True, slots=True)
class ExecutionPolicySnapshot:
    """Execution policy values frozen when an Execution is created."""

    timeout: Duration | None = None


class FailureCategory(StrEnum):
    """Normalized high-level failure category."""

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Failure:
    """Normalized execution failure, distinct from a Python exception."""

    category: FailureCategory
    code: str
    message: str
    occurred_at: Instant
    retryable_hint: bool | None = None
    details: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("Failure code must not be empty.")
        if not self.message.strip():
            raise ValueError("Failure message must not be empty.")


class AttemptState(StrEnum):
    """Lifecycle state of one concrete execution Attempt."""

    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class AttemptResult:
    """Immutable terminal result of one Attempt."""

    state: AttemptState
    completed_at: Instant
    failure: Failure | None = None

    def __post_init__(self) -> None:
        if self.state is AttemptState.RUNNING:
            raise ValueError("AttemptResult must be terminal.")

        if self.state is AttemptState.SUCCESS and self.failure is not None:
            raise ValueError("Successful AttemptResult cannot contain a Failure.")

        if self.state is not AttemptState.SUCCESS and self.failure is None:
            raise ValueError("Non-success AttemptResult requires a Failure.")


class Attempt:
    """Entity representing one concrete try within an Execution."""

    __slots__ = (
        "_execution_id",
        "_id",
        "_number",
        "_result",
        "_started_at",
        "_state",
        "_version",
    )

    def __init__(
        self,
        *,
        attempt_id: AttemptId,
        execution_id: ExecutionId,
        number: int,
        started_at: Instant,
        state: AttemptState = AttemptState.RUNNING,
        result: AttemptResult | None = None,
        version: int = 0,
    ) -> None:
        if number < 1:
            raise ValueError("Attempt number must be greater than or equal to 1.")
        if version < 0:
            raise ValueError("Attempt version must be non-negative.")
        if state is AttemptState.RUNNING and result is not None:
            raise ValueError("Running Attempt cannot already have a result.")
        if state is not AttemptState.RUNNING and result is None:
            raise ValueError("Terminal Attempt requires a result.")

        self._id = attempt_id
        self._execution_id = execution_id
        self._number = number
        self._started_at = started_at
        self._state = state
        self._result = result
        self._version = version

    @classmethod
    def start(
        cls,
        *,
        execution_id: ExecutionId,
        number: int,
        started_at: Instant,
    ) -> Attempt:
        return cls(
            attempt_id=AttemptId.for_execution(execution_id, number),
            execution_id=execution_id,
            number=number,
            started_at=started_at,
        )

    @property
    def id(self) -> AttemptId:
        return self._id

    @property
    def execution_id(self) -> ExecutionId:
        return self._execution_id

    @property
    def number(self) -> int:
        return self._number

    @property
    def started_at(self) -> Instant:
        return self._started_at

    @property
    def state(self) -> AttemptState:
        return self._state

    @property
    def result(self) -> AttemptResult | None:
        return self._result

    @property
    def version(self) -> int:
        return self._version

    @property
    def is_terminal(self) -> bool:
        return self._state is not AttemptState.RUNNING

    def succeed(self, *, completed_at: Instant) -> AttemptResult:
        return self._complete(
            AttemptResult(
                state=AttemptState.SUCCESS,
                completed_at=completed_at,
            )
        )

    def fail(self, *, failure: Failure, completed_at: Instant) -> AttemptResult:
        return self._complete(
            AttemptResult(
                state=AttemptState.FAILED,
                completed_at=completed_at,
                failure=failure,
            )
        )

    def timeout(self, *, completed_at: Instant) -> AttemptResult:
        return self._complete(
            AttemptResult(
                state=AttemptState.TIMED_OUT,
                completed_at=completed_at,
                failure=Failure(
                    category=FailureCategory.TIMEOUT,
                    code="execution.timeout",
                    message="Execution attempt timed out.",
                    occurred_at=completed_at,
                    retryable_hint=True,
                ),
            )
        )

    def cancel(self, *, completed_at: Instant) -> AttemptResult:
        return self._complete(
            AttemptResult(
                state=AttemptState.CANCELLED,
                completed_at=completed_at,
                failure=Failure(
                    category=FailureCategory.CANCELLED,
                    code="execution.cancelled",
                    message="Execution attempt was cancelled.",
                    occurred_at=completed_at,
                    retryable_hint=False,
                ),
            )
        )

    def _complete(self, result: AttemptResult) -> AttemptResult:
        if self._state is not AttemptState.RUNNING:
            raise InvalidAttemptTransitionError(
                f"Cannot complete Attempt from state {self._state.value!r}."
            )

        self._state = result.state
        self._result = result
        self._version += 1
        return result


class ExecutionState(StrEnum):
    """Lifecycle state of one logical Execution."""

    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Immutable terminal result of an Execution."""

    state: ExecutionState
    completed_at: Instant
    failure: Failure | None = None

    def __post_init__(self) -> None:
        if self.state not in (
            ExecutionState.SUCCESS,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
            ExecutionState.TIMED_OUT,
        ):
            raise ValueError("ExecutionResult must use a terminal Execution state.")

        if self.state is ExecutionState.SUCCESS and self.failure is not None:
            raise ValueError("Successful ExecutionResult cannot contain a Failure.")

        if self.state is not ExecutionState.SUCCESS and self.failure is None:
            raise ValueError("Non-success ExecutionResult requires a Failure.")


class Execution:
    """Aggregate Root for one logical execution across one or more Attempts."""

    __slots__ = (
        "_active_attempt_number",
        "_attempt_count",
        "_created_at",
        "_id",
        "_idempotency_key",
        "_next_attempt_at",
        "_policy_snapshot",
        "_request_id",
        "_result",
        "_state",
        "_target",
        "_version",
    )

    def __init__(
        self,
        *,
        execution_id: ExecutionId,
        request_id: RequestId,
        target: TargetRef,
        created_at: Instant,
        policy_snapshot: ExecutionPolicySnapshot,
        idempotency_key: IdempotencyKey,
        state: ExecutionState = ExecutionState.QUEUED,
        version: int = 0,
        attempt_count: int = 0,
        active_attempt_number: int | None = None,
        next_attempt_at: Instant | None = None,
        result: ExecutionResult | None = None,
    ) -> None:
        if version < 0:
            raise ValueError("Execution version must be non-negative.")
        if attempt_count < 0:
            raise ValueError("attempt_count must be non-negative.")

        self._id = execution_id
        self._request_id = request_id
        self._target = target
        self._created_at = created_at
        self._policy_snapshot = policy_snapshot
        self._idempotency_key = idempotency_key
        self._state = state
        self._version = version
        self._attempt_count = attempt_count
        self._active_attempt_number = active_attempt_number
        self._next_attempt_at = next_attempt_at
        self._result = result
        self._assert_invariants()

    @classmethod
    def from_request(
        cls,
        *,
        request: ExecutionRequest,
        created_at: Instant,
        policy_snapshot: ExecutionPolicySnapshot | None = None,
    ) -> Execution:
        if request.state is not ExecutionRequestState.DISPATCHED:
            raise InvalidExecutionTransitionError(
                "Execution can only be created from a dispatched ExecutionRequest."
            )

        return cls(
            execution_id=ExecutionId.for_request(request.id),
            request_id=request.id,
            target=request.target,
            created_at=created_at,
            policy_snapshot=policy_snapshot or ExecutionPolicySnapshot(),
            idempotency_key=IdempotencyKey.for_request(request.id),
        )

    @property
    def id(self) -> ExecutionId:
        return self._id

    @property
    def request_id(self) -> RequestId:
        return self._request_id

    @property
    def target(self) -> TargetRef:
        return self._target

    @property
    def created_at(self) -> Instant:
        return self._created_at

    @property
    def policy_snapshot(self) -> ExecutionPolicySnapshot:
        return self._policy_snapshot

    @property
    def idempotency_key(self) -> IdempotencyKey:
        return self._idempotency_key

    @property
    def state(self) -> ExecutionState:
        return self._state

    @property
    def version(self) -> int:
        return self._version

    @property
    def attempt_count(self) -> int:
        return self._attempt_count

    @property
    def active_attempt_number(self) -> int | None:
        return self._active_attempt_number

    @property
    def next_attempt_at(self) -> Instant | None:
        return self._next_attempt_at

    @property
    def result(self) -> ExecutionResult | None:
        return self._result

    @property
    def is_terminal(self) -> bool:
        return self._result is not None

    def start_attempt(self, *, started_at: Instant) -> Attempt:
        if self._state not in (ExecutionState.QUEUED, ExecutionState.RETRY_WAIT):
            raise InvalidExecutionTransitionError(
                f"Cannot start Attempt from Execution state {self._state.value!r}."
            )
        if self._active_attempt_number is not None:
            raise InvalidExecutionTransitionError("Execution already has an active Attempt.")
        if self._state is ExecutionState.RETRY_WAIT:
            if self._next_attempt_at is None:
                raise InvalidExecutionTransitionError(
                    "RETRY_WAIT Execution must have next_attempt_at."
                )
            if started_at < self._next_attempt_at:
                raise InvalidExecutionTransitionError(
                    "Retry Attempt cannot start before next_attempt_at."
                )

        self._attempt_count += 1
        self._active_attempt_number = self._attempt_count
        self._next_attempt_at = None
        self._state = ExecutionState.RUNNING
        self._version += 1

        return Attempt.start(
            execution_id=self._id,
            number=self._attempt_count,
            started_at=started_at,
        )

    def finish_attempt(
        self,
        *,
        attempt: Attempt,
        retry_at: Instant | None = None,
    ) -> ExecutionResult | None:
        if self._state is not ExecutionState.RUNNING:
            raise InvalidExecutionTransitionError(
                f"Cannot finish Attempt from Execution state {self._state.value!r}."
            )
        if self._active_attempt_number != attempt.number:
            raise InvalidExecutionTransitionError(
                "Attempt number does not match the active Execution Attempt."
            )
        if attempt.execution_id != self._id:
            raise InvalidExecutionTransitionError("Attempt belongs to a different Execution.")
        if not attempt.is_terminal or attempt.result is None:
            raise InvalidExecutionTransitionError(
                "Attempt must be terminal before finishing it on Execution."
            )

        result = attempt.result
        self._active_attempt_number = None

        if retry_at is not None:
            if result.state not in (AttemptState.FAILED, AttemptState.TIMED_OUT):
                raise InvalidExecutionTransitionError(
                    "Only failed or timed-out Attempts may enter RETRY_WAIT."
                )
            self._state = ExecutionState.RETRY_WAIT
            self._next_attempt_at = retry_at
            self._version += 1
            self._assert_invariants()
            return None

        execution_state = {
            AttemptState.SUCCESS: ExecutionState.SUCCESS,
            AttemptState.FAILED: ExecutionState.FAILED,
            AttemptState.TIMED_OUT: ExecutionState.TIMED_OUT,
            AttemptState.CANCELLED: ExecutionState.CANCELLED,
        }[result.state]

        execution_result = ExecutionResult(
            state=execution_state,
            completed_at=result.completed_at,
            failure=result.failure,
        )
        self._state = execution_state
        self._result = execution_result
        self._next_attempt_at = None
        self._version += 1
        self._assert_invariants()
        return execution_result

    def cancel(self, *, completed_at: Instant) -> ExecutionResult:
        if self._state is ExecutionState.CANCELLED and self._result is not None:
            return self._result
        if self._state not in (ExecutionState.QUEUED, ExecutionState.RETRY_WAIT):
            raise InvalidExecutionTransitionError(
                f"Cannot directly cancel Execution from state {self._state.value!r}."
            )

        result = ExecutionResult(
            state=ExecutionState.CANCELLED,
            completed_at=completed_at,
            failure=Failure(
                category=FailureCategory.CANCELLED,
                code="execution.cancelled",
                message="Execution was cancelled before a running Attempt completed.",
                occurred_at=completed_at,
                retryable_hint=False,
            ),
        )
        self._state = ExecutionState.CANCELLED
        self._result = result
        self._next_attempt_at = None
        self._version += 1
        self._assert_invariants()
        return result

    def _assert_invariants(self) -> None:
        terminal_states = {
            ExecutionState.SUCCESS,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
            ExecutionState.TIMED_OUT,
        }

        if self._state in terminal_states and self._result is None:
            raise ValueError("Terminal Execution requires an ExecutionResult.")

        if self._state not in terminal_states and self._result is not None:
            raise ValueError("Non-terminal Execution cannot have an ExecutionResult.")

        if self._state is ExecutionState.RUNNING and self._active_attempt_number is None:
            raise ValueError("RUNNING Execution requires an active Attempt number.")

        if self._state is not ExecutionState.RUNNING and self._active_attempt_number is not None:
            raise ValueError("Only RUNNING Execution may have an active Attempt number.")

        if self._state is ExecutionState.RETRY_WAIT and self._next_attempt_at is None:
            raise ValueError("RETRY_WAIT Execution requires next_attempt_at.")

        if self._state is not ExecutionState.RETRY_WAIT and self._next_attempt_at is not None:
            raise ValueError("Only RETRY_WAIT Execution may have next_attempt_at.")
