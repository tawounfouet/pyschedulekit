"""Persistence ports for Schedule storage and transactional boundaries."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol

from pyschedulekit.domain.schedule import Schedule, ScheduleId
from pyschedulekit.domain.time import Instant


class PersistenceConflictError(RuntimeError):
    """Base error for optimistic or uniqueness conflicts."""


class OptimisticConcurrencyError(PersistenceConflictError):
    """Raised when committed state changed since a Schedule was loaded."""


class DuplicateScheduleError(PersistenceConflictError):
    """Raised when a new Schedule uses an already committed ScheduleId."""


class UntrackedScheduleError(RuntimeError):
    """Raised when attempting to save a Schedule not loaded by this UnitOfWork."""


class ScheduleRepository(Protocol):
    """Transactional repository for Schedule aggregates."""

    def add(self, schedule: Schedule) -> None:
        """Stage a new Schedule for insertion."""
        ...

    def get(self, schedule_id: ScheduleId) -> Schedule | None:
        """Load one Schedule into the current UnitOfWork identity map."""
        ...

    def save(self, schedule: Schedule) -> None:
        """Stage an already-loaded Schedule for update."""
        ...

    def list_due(self, *, now: Instant, limit: int) -> list[Schedule]:
        """Load active Schedules due at or before now in deterministic order."""
        ...


class UnitOfWork(Protocol):
    """Transactional boundary owning Schedule repository changes."""

    schedules: ScheduleRepository

    def __enter__(self) -> UnitOfWork: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    def commit(self) -> None:
        """Atomically publish staged changes."""
        ...

    def rollback(self) -> None:
        """Discard every staged change."""
        ...


class UnitOfWorkFactory(Protocol):
    """Callable factory producing independent UnitOfWork instances."""

    def __call__(self) -> UnitOfWork: ...
