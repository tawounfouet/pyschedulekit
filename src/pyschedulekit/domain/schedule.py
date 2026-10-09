"""Schedule aggregate and scheduling definition value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from pyschedulekit.domain.concurrency import ConcurrencyPolicy
from pyschedulekit.domain.misfire import MisfirePolicy
from pyschedulekit.domain.retry import RetryPolicy
from pyschedulekit.domain.time import Duration, Instant, Timezone
from pyschedulekit.domain.trigger import Trigger


class InvalidScheduleTransitionError(ValueError):
    """Raised when a Schedule lifecycle transition is not allowed."""


class InvalidScheduleOperationError(ValueError):
    """Raised when a Schedule operation would violate an aggregate invariant."""


class InvalidTargetRefError(ValueError):
    """Raised when a TargetRef is empty or malformed."""


@dataclass(frozen=True, slots=True)
class ScheduleId:
    """Stable identity of one Schedule aggregate."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("ScheduleId must not be empty.")


@dataclass(frozen=True, slots=True, order=True)
class ScheduleRevision:
    """Version of the functional Schedule definition."""

    value: int = 1

    def __post_init__(self) -> None:
        if self.value < 1:
            raise ValueError("ScheduleRevision must be greater than or equal to 1.")

    def next(self) -> ScheduleRevision:
        return ScheduleRevision(self.value + 1)


@dataclass(frozen=True, slots=True, order=True)
class PersistenceVersion:
    """Optimistic-concurrency version of the durable Schedule record."""

    value: int = 0

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("PersistenceVersion must be greater than or equal to 0.")

    def next(self) -> PersistenceVersion:
        return PersistenceVersion(self.value + 1)


class ScheduleState(StrEnum):
    """Lifecycle state of a Schedule aggregate."""

    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class TargetRef:
    """Declarative reference to work that may be resolved by a later executor."""

    kind: str
    reference: str

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise InvalidTargetRefError("TargetRef kind must not be empty.")
        if not self.reference.strip():
            raise InvalidTargetRefError("TargetRef reference must not be empty.")

    @classmethod
    def python(cls, reference: str) -> TargetRef:
        return cls(kind="python", reference=reference)

    @classmethod
    def async_python(cls, reference: str) -> TargetRef:
        return cls(kind="python_async", reference=reference)

    @classmethod
    def workflow(cls, reference: str) -> TargetRef:
        return cls(kind="workflow", reference=reference)

    @classmethod
    def http(cls, reference: str) -> TargetRef:
        return cls(kind="http", reference=reference)


@dataclass(frozen=True, slots=True)
class ScheduleDefinition:
    """Immutable functional definition of a Schedule."""

    target: TargetRef
    trigger: Trigger
    timezone: Timezone = field(default_factory=lambda: Timezone("UTC"))
    misfire: MisfirePolicy = field(default_factory=MisfirePolicy.run_now)
    concurrency: ConcurrencyPolicy = field(default_factory=ConcurrencyPolicy.allow)
    retry: RetryPolicy = field(default_factory=RetryPolicy.none)
    timeout: Duration | None = None

    def __post_init__(self) -> None:
        if self.timeout is not None and self.timeout.total_seconds <= 0:
            raise ValueError("Schedule timeout must be greater than zero.")


class Schedule:
    """Aggregate Root controlling Schedule lifecycle and operational checkpoint."""

    __slots__ = (
        "_definition",
        "_id",
        "_next_run_time",
        "_persistence_version",
        "_revision",
        "_state",
    )

    def __init__(
        self,
        *,
        schedule_id: ScheduleId,
        definition: ScheduleDefinition,
        state: ScheduleState,
        revision: ScheduleRevision,
        persistence_version: PersistenceVersion,
        next_run_time: Instant | None,
    ) -> None:
        self._id = schedule_id
        self._definition = definition
        self._state = state
        self._revision = revision
        self._persistence_version = persistence_version
        self._next_run_time = next_run_time
        self._assert_invariants()

    @classmethod
    def create(
        cls,
        *,
        schedule_id: ScheduleId,
        definition: ScheduleDefinition,
        reference: Instant,
    ) -> Schedule:
        """Create a Schedule and calculate its first future occurrence."""

        next_run_time = definition.trigger.next_after(reference)
        state = ScheduleState.COMPLETED if next_run_time is None else ScheduleState.ACTIVE

        return cls(
            schedule_id=schedule_id,
            definition=definition,
            state=state,
            revision=ScheduleRevision(),
            persistence_version=PersistenceVersion(),
            next_run_time=next_run_time,
        )

    @property
    def id(self) -> ScheduleId:
        return self._id

    @property
    def definition(self) -> ScheduleDefinition:
        return self._definition

    @property
    def state(self) -> ScheduleState:
        return self._state

    @property
    def revision(self) -> ScheduleRevision:
        return self._revision

    @property
    def persistence_version(self) -> PersistenceVersion:
        return self._persistence_version

    @property
    def next_run_time(self) -> Instant | None:
        return self._next_run_time

    def pause(self) -> None:
        """Pause future occurrence materialization."""

        if self._state is ScheduleState.PAUSED:
            return
        if self._state is not ScheduleState.ACTIVE:
            raise InvalidScheduleTransitionError(
                f"Cannot pause Schedule from state {self._state.value!r}."
            )

        self._state = ScheduleState.PAUSED
        self._next_run_time = None
        self._touch()

    def resume(self, *, reference: Instant) -> None:
        """Resume from current time without implicitly catching up paused time."""

        if self._state is ScheduleState.ACTIVE:
            return
        if self._state is not ScheduleState.PAUSED:
            raise InvalidScheduleTransitionError(
                f"Cannot resume Schedule from state {self._state.value!r}."
            )

        next_run_time = self._definition.trigger.next_after(reference)
        self._next_run_time = next_run_time
        self._state = ScheduleState.COMPLETED if next_run_time is None else ScheduleState.ACTIVE
        self._touch()

    def cancel(self) -> None:
        """Cancel future scheduling without implying execution cancellation."""

        if self._state is ScheduleState.CANCELLED:
            return
        if self._state not in (ScheduleState.ACTIVE, ScheduleState.PAUSED):
            raise InvalidScheduleTransitionError(
                f"Cannot cancel Schedule from state {self._state.value!r}."
            )

        self._state = ScheduleState.CANCELLED
        self._next_run_time = None
        self._touch()

    def complete(self) -> None:
        """Mark an active Schedule completed after trigger exhaustion."""

        if self._state is ScheduleState.COMPLETED:
            return
        if self._state is not ScheduleState.ACTIVE:
            raise InvalidScheduleTransitionError(
                f"Cannot complete Schedule from state {self._state.value!r}."
            )

        self._state = ScheduleState.COMPLETED
        self._next_run_time = None
        self._touch()

    def reschedule(
        self,
        *,
        definition: ScheduleDefinition,
        reference: Instant,
    ) -> None:
        """Replace the functional definition while preserving Schedule identity."""

        if self._state in (ScheduleState.CANCELLED, ScheduleState.COMPLETED):
            raise InvalidScheduleTransitionError(
                f"Cannot reschedule Schedule from state {self._state.value!r}."
            )

        self._definition = definition
        self._revision = self._revision.next()

        if self._state is ScheduleState.ACTIVE:
            next_run_time = definition.trigger.next_after(reference)
            self._next_run_time = next_run_time
            if next_run_time is None:
                self._state = ScheduleState.COMPLETED
        else:
            self._next_run_time = None

        self._touch()
        self._assert_invariants()

    def advance_next_run_after(self, *, reference: Instant) -> Instant | None:
        """Advance the operational checkpoint without changing ScheduleRevision."""

        if self._state is not ScheduleState.ACTIVE:
            raise InvalidScheduleOperationError(
                "Only an active Schedule can advance its next_run_time."
            )

        if self._next_run_time is not None and reference < self._next_run_time:
            raise InvalidScheduleOperationError(
                "Cannot advance next_run_time from a reference before the current checkpoint."
            )

        next_run_time = self._definition.trigger.next_after(reference)
        self._next_run_time = next_run_time
        if next_run_time is None:
            self._state = ScheduleState.COMPLETED

        self._touch()
        self._assert_invariants()
        return next_run_time

    def _touch(self) -> None:
        self._persistence_version = self._persistence_version.next()

    def _assert_invariants(self) -> None:
        if self._state is ScheduleState.ACTIVE and self._next_run_time is None:
            raise InvalidScheduleOperationError("An active Schedule must have a next_run_time.")

        if self._state is not ScheduleState.ACTIVE and self._next_run_time is not None:
            raise InvalidScheduleOperationError(
                "Only an active Schedule may expose a next_run_time."
            )
