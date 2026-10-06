"""Transactional in-memory persistence adapters."""

from __future__ import annotations

from threading import RLock
from types import TracebackType

from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.schedule import (
    PersistenceVersion,
    Schedule,
    ScheduleId,
    ScheduleState,
)
from pyschedulekit.domain.time import Instant
from pyschedulekit.ports.persistence import (
    DuplicateExecutionRequestError,
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


class InMemoryStore:
    """Shared committed state backing independent in-memory UnitOfWork instances."""

    def __init__(self) -> None:
        self._schedules: dict[ScheduleId, Schedule] = {}
        self._execution_requests: dict[RequestId, ExecutionRequest] = {}
        self._request_by_occurrence: dict[OccurrenceKey, RequestId] = {}
        self._lock = RLock()


InMemoryScheduleStore = InMemoryStore


class InMemoryScheduleRepository:
    """Schedule repository with an identity map and staged write set."""

    def __init__(self, store: InMemoryStore) -> None:
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

    def _apply_commit_locked(self) -> None:
        for schedule_id in self._new:
            self._store._schedules[schedule_id] = _clone_schedule(self._tracked[schedule_id])

        for schedule_id in self._dirty:
            self._store._schedules[schedule_id] = _clone_schedule(self._tracked[schedule_id])

    def _after_commit(self) -> None:
        for schedule_id in self._new | self._dirty:
            self._expected_versions[schedule_id] = self._tracked[schedule_id].persistence_version

        self._new.clear()
        self._dirty.clear()

    def _rollback(self) -> None:
        self._tracked.clear()
        self._expected_versions.clear()
        self._new.clear()
        self._dirty.clear()


class InMemoryExecutionRequestRepository:
    """Immutable ExecutionRequest repository with occurrence uniqueness."""

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store
        self._new: dict[RequestId, ExecutionRequest] = {}
        self._new_by_occurrence: dict[OccurrenceKey, RequestId] = {}

    def add(self, request: ExecutionRequest) -> None:
        if request.id in self._new:
            raise DuplicateExecutionRequestError(
                f"ExecutionRequest {request.id.value!r} is already staged."
            )
        if request.occurrence_key in self._new_by_occurrence:
            raise DuplicateExecutionRequestError(
                "An ExecutionRequest for this OccurrenceKey is already staged."
            )

        self._new[request.id] = request
        self._new_by_occurrence[request.occurrence_key] = request.id

    def get(self, request_id: RequestId) -> ExecutionRequest | None:
        staged = self._new.get(request_id)
        if staged is not None:
            return staged

        with self._store._lock:
            return self._store._execution_requests.get(request_id)

    def get_by_occurrence(self, key: OccurrenceKey) -> ExecutionRequest | None:
        staged_id = self._new_by_occurrence.get(key)
        if staged_id is not None:
            return self._new[staged_id]

        with self._store._lock:
            committed_id = self._store._request_by_occurrence.get(key)
            if committed_id is None:
                return None
            return self._store._execution_requests[committed_id]

    def _validate_commit_locked(self) -> None:
        for request in self._new.values():
            if request.id in self._store._execution_requests:
                raise DuplicateExecutionRequestError(
                    f"ExecutionRequest {request.id.value!r} already exists."
                )

            if request.occurrence_key in self._store._request_by_occurrence:
                raise DuplicateExecutionRequestError(
                    "An ExecutionRequest for this OccurrenceKey already exists."
                )

    def _apply_commit_locked(self) -> None:
        for request in self._new.values():
            self._store._execution_requests[request.id] = request
            self._store._request_by_occurrence[request.occurrence_key] = request.id

    def _after_commit(self) -> None:
        self._new.clear()
        self._new_by_occurrence.clear()

    def _rollback(self) -> None:
        self._new.clear()
        self._new_by_occurrence.clear()


class InMemoryUnitOfWork:
    """Explicit transaction across Schedule and ExecutionRequest repositories."""

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store
        self._active = False
        self.schedules = InMemoryScheduleRepository(store)
        self.requests = InMemoryExecutionRequestRepository(store)

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
    ) -> None:
        del exc_type, exc, traceback
        self.rollback()
        self._active = False

    def commit(self) -> None:
        self._require_active()

        with self._store._lock:
            self.schedules._validate_commit_locked()
            self.requests._validate_commit_locked()

            self.schedules._apply_commit_locked()
            self.requests._apply_commit_locked()

            self.schedules._after_commit()
            self.requests._after_commit()

    def rollback(self) -> None:
        self.schedules._rollback()
        self.requests._rollback()

    def _require_active(self) -> None:
        if not self._active:
            raise RuntimeError("UnitOfWork must be entered before commit().")


class InMemoryUnitOfWorkFactory:
    """Factory sharing one committed store across independent transactions."""

    def __init__(self, store: InMemoryStore | None = None) -> None:
        self._store = store or InMemoryStore()

    def __call__(self) -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork(self._store)
