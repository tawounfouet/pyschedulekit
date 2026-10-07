"""Durable scheduling intent created from one logical Occurrence."""

from __future__ import annotations

from enum import StrEnum
from hashlib import sha256

from pyschedulekit.domain.concurrency import ConcurrencyPolicy
from pyschedulekit.domain.occurrence import Occurrence, OccurrenceKey
from pyschedulekit.domain.retry import RetryPolicy
from pyschedulekit.domain.schedule import TargetRef
from pyschedulekit.domain.time import Duration, Instant


class InvalidExecutionRequestTransitionError(ValueError):
    """Raised when an ExecutionRequest state transition is invalid."""


class RequestId:
    """Stable identity for a scheduler-created ExecutionRequest."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        if not value.strip():
            raise ValueError("RequestId must not be empty.")
        self._value = value

    @property
    def value(self) -> str:
        return self._value

    @classmethod
    def for_occurrence(cls, key: OccurrenceKey) -> RequestId:
        canonical = "|".join(
            (
                key.schedule_id.value,
                str(key.schedule_revision.value),
                key.scheduled_at.value.isoformat(),
            )
        )
        return cls(sha256(canonical.encode("utf-8")).hexdigest())

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RequestId) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __repr__(self) -> str:
        return f"RequestId({self.value!r})"


class ExecutionRequestState(StrEnum):
    """Lifecycle state of a durable execution intent."""

    PENDING = "pending"
    WAITING_ADMISSION = "waiting_admission"
    DISPATCHED = "dispatched"
    DROPPED = "dropped"
    CANCELLED = "cancelled"


class ExecutionRequest:
    """Entity controlling the lifecycle of one durable execution intent."""

    __slots__ = (
        "_concurrency_policy",
        "_created_at",
        "_id",
        "_occurrence_key",
        "_retry_policy",
        "_state",
        "_target",
        "_timeout",
        "_version",
    )

    def __init__(
        self,
        *,
        id: RequestId,
        occurrence_key: OccurrenceKey,
        target: TargetRef,
        created_at: Instant,
        concurrency_policy: ConcurrencyPolicy | None = None,
        retry_policy: RetryPolicy | None = None,
        timeout: Duration | None = None,
        state: ExecutionRequestState = ExecutionRequestState.PENDING,
        version: int = 0,
    ) -> None:
        if version < 0:
            raise ValueError("ExecutionRequest version must be non-negative.")

        self._id = id
        self._occurrence_key = occurrence_key
        self._target = target
        self._created_at = created_at
        self._concurrency_policy = concurrency_policy or ConcurrencyPolicy.allow()
        self._retry_policy = retry_policy or RetryPolicy.none()
        if timeout is not None and timeout.total_seconds <= 0:
            raise ValueError("ExecutionRequest timeout must be greater than zero.")
        self._timeout = timeout
        self._state = state
        self._version = version

    @classmethod
    def from_occurrence(
        cls,
        *,
        occurrence: Occurrence,
        target: TargetRef,
        created_at: Instant,
        concurrency_policy: ConcurrencyPolicy | None = None,
        retry_policy: RetryPolicy | None = None,
        timeout: Duration | None = None,
    ) -> ExecutionRequest:
        return cls(
            id=RequestId.for_occurrence(occurrence.key),
            occurrence_key=occurrence.key,
            target=target,
            created_at=created_at,
            concurrency_policy=concurrency_policy,
            retry_policy=retry_policy,
            timeout=timeout,
        )

    @property
    def id(self) -> RequestId:
        return self._id

    @property
    def occurrence_key(self) -> OccurrenceKey:
        return self._occurrence_key

    @property
    def target(self) -> TargetRef:
        return self._target

    @property
    def created_at(self) -> Instant:
        return self._created_at

    @property
    def concurrency_policy(self) -> ConcurrencyPolicy:
        return self._concurrency_policy

    @property
    def retry_policy(self) -> RetryPolicy:
        return self._retry_policy

    @property
    def timeout(self) -> Duration | None:
        return self._timeout

    @property
    def state(self) -> ExecutionRequestState:
        return self._state

    @property
    def version(self) -> int:
        return self._version

    def wait_for_admission(self) -> None:
        if self._state is ExecutionRequestState.WAITING_ADMISSION:
            return
        if self._state is not ExecutionRequestState.PENDING:
            raise InvalidExecutionRequestTransitionError(
                f"Cannot wait for admission from state {self._state.value!r}."
            )
        self._transition(ExecutionRequestState.WAITING_ADMISSION)

    def mark_dispatched(self) -> None:
        if self._state is ExecutionRequestState.DISPATCHED:
            return
        if self._state not in (
            ExecutionRequestState.PENDING,
            ExecutionRequestState.WAITING_ADMISSION,
        ):
            raise InvalidExecutionRequestTransitionError(
                f"Cannot dispatch request from state {self._state.value!r}."
            )
        self._transition(ExecutionRequestState.DISPATCHED)

    def drop(self) -> None:
        if self._state is ExecutionRequestState.DROPPED:
            return
        if self._state not in (
            ExecutionRequestState.PENDING,
            ExecutionRequestState.WAITING_ADMISSION,
        ):
            raise InvalidExecutionRequestTransitionError(
                f"Cannot drop request from state {self._state.value!r}."
            )
        self._transition(ExecutionRequestState.DROPPED)

    def cancel(self) -> None:
        if self._state is ExecutionRequestState.CANCELLED:
            return
        if self._state not in (
            ExecutionRequestState.PENDING,
            ExecutionRequestState.WAITING_ADMISSION,
        ):
            raise InvalidExecutionRequestTransitionError(
                f"Cannot cancel request from state {self._state.value!r}."
            )
        self._transition(ExecutionRequestState.CANCELLED)

    def _transition(self, state: ExecutionRequestState) -> None:
        self._state = state
        self._version += 1

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExecutionRequest):
            return False
        return (
            self.id == other.id
            and self.occurrence_key == other.occurrence_key
            and self.target == other.target
            and self.created_at == other.created_at
            and self.concurrency_policy == other.concurrency_policy
            and self.retry_policy == other.retry_policy
            and self.timeout == other.timeout
            and self.state == other.state
            and self.version == other.version
        )
