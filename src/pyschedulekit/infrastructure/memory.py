"""Transactional in-memory persistence adapters."""

from __future__ import annotations

from threading import RLock
from types import TracebackType

from pyschedulekit.domain.schedule import (
    PersistenceVersion,
    Schedule,
    ScheduleId,
    ScheduleState,
)
from pyschedulekit.domain.time import Instant
from pyschedulekit.ports.persistence import (
    DuplicateScheduleError,
    OptimisticConcurrencyError,
    UntrackedScheduleError,
)


def _clone_schedule(schedule: Schedule) -> Schedule:
    """Rehydrate an independent aggregate instance from committed state."""

    return Schedule(
        schedule_id=schedule.id,
        definition=schedule.definition,
        state=schedule.state,
        revision=schedule.revision,
        persistence_version=schedule.persistence_version,
        next_run_time=schedule.next_run_time,
    )


class InMemoryScheduleStore:
    """Shared committed state backing independent in-memory UnitOfWork instances."""

    def __init__(self) -> None:
        self._schedules: dict[ScheduleId, Schedule] = {}
        self._lock = RLock()


class InMemoryScheduleRepository:
    """Schedule repository with an identity map and staged write set."""

    def __init__(self, store: InMemoryScheduleStore) -> None:
        self._store = store
        self._tracked: dict[ScheduleId, Schedule] = {}
        self._expected_versions: dict[ScheduleId, PersistenceVersion] = {}
        self._new: set[ScheduleId] = set()
        self._dirty: set[ScheduleId] = set()

    def add(self, schedule: Schedule) -> None:
        schedule_id = schedule.id
        if schedule_id in self._tracked:
            raise DuplicateScheduleError(
                f"Schedule {schedule_id.value!r} is already tracked by this UnitOfWork."
            )

        self._tracked[schedule_id] = schedule
        self._new.add(schedule_id)

    def get(self, schedule_id: ScheduleId) -> Schedule | None:
        tracked = self._tracked.get(schedule_id)
        if tracked is not None:
            return tracked

        with self._store._lock:
            committed = self._store._schedules.get(schedule_id)
            if committed is None:
                return None

            loaded = _clone_schedule(committed)
            self._tracked[schedule_id] = loaded
            self._expected_versions[schedule_id] = committed.persistence_version
            return loaded

    def save(self, schedule: Schedule) -> None:
        schedule_id = schedule.id
        tracked = self._tracked.get(schedule_id)

        if tracked is not schedule:
            raise UntrackedScheduleError(
                f"Schedule {schedule_id.value!r} must be loaded by this UnitOfWork before save()."
            )

        if schedule_id in self._new:
            return

        if schedule_id not in self._expected_versions:
            raise UntrackedScheduleError(
                f"Schedule {schedule_id.value!r} has no tracked committed version."
            )

        self._dirty.add(schedule_id)

    def list_due(self, *, now: Instant, limit: int) -> list[Schedule]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        with self._store._lock:
            candidate_ids = set(self._store._schedules)

        candidate_ids.update(self._tracked)

        due: list[Schedule] = []
        for schedule_id in candidate_ids:
            schedule = self._tracked.get(schedule_id)
            if schedule is None:
                schedule = self.get(schedule_id)
            if schedule is None:
                continue
            if schedule.state is not ScheduleState.ACTIVE:
                continue
            if schedule.next_run_time is None or schedule.next_run_time > now:
                continue
            due.append(schedule)

        due.sort(
            key=lambda schedule: (
                schedule.next_run_time.value if schedule.next_run_time is not None else now.value,
                schedule.id.value,
            )
        )
        return due[:limit]

    def _commit(self) -> None:
        with self._store._lock:
            self._validate_commit_locked()

            for schedule_id in self._new:
                schedule = self._tracked[schedule_id]
                self._store._schedules[schedule_id] = _clone_schedule(schedule)

            for schedule_id in self._dirty:
                schedule = self._tracked[schedule_id]
                self._store._schedules[schedule_id] = _clone_schedule(schedule)

            for schedule_id in self._new | self._dirty:
                self._expected_versions[schedule_id] = self._tracked[
                    schedule_id
                ].persistence_version

            self._new.clear()
            self._dirty.clear()

    def _validate_commit_locked(self) -> None:
        for schedule_id in self._new:
            if schedule_id in self._store._schedules:
                raise DuplicateScheduleError(f"Schedule {schedule_id.value!r} already exists.")

        for schedule_id in self._dirty:
            committed = self._store._schedules.get(schedule_id)
            expected = self._expected_versions[schedule_id]

            if committed is None:
                raise OptimisticConcurrencyError(
                    f"Schedule {schedule_id.value!r} was deleted after it was loaded."
                )

            if committed.persistence_version != expected:
                raise OptimisticConcurrencyError(
                    f"Schedule {schedule_id.value!r} changed concurrently: "
                    f"expected version {expected.value}, "
                    f"found {committed.persistence_version.value}."
                )

    def _rollback(self) -> None:
        self._tracked.clear()
        self._expected_versions.clear()
        self._new.clear()
        self._dirty.clear()


class InMemoryUnitOfWork:
    """Explicit transactional boundary over an InMemoryScheduleStore."""

    def __init__(self, store: InMemoryScheduleStore) -> None:
        self._store = store
        self._active = False
        self.schedules = InMemoryScheduleRepository(store)

    def __enter__(self) -> InMemoryUnitOfWork:
        if self._active:
            raise RuntimeError("UnitOfWork is already active.")
        self._active = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        del exc_type, exc, traceback
        self.rollback()
        self._active = False
        return False

    def commit(self) -> None:
        self._require_active()
        self.schedules._commit()

    def rollback(self) -> None:
        self.schedules._rollback()

    def _require_active(self) -> None:
        if not self._active:
            raise RuntimeError("UnitOfWork must be entered before commit().")


class InMemoryUnitOfWorkFactory:
    """Factory sharing one committed store across independent transactions."""

    def __init__(self, store: InMemoryScheduleStore | None = None) -> None:
        self._store = store or InMemoryScheduleStore()

    def __call__(self) -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork(self._store)
