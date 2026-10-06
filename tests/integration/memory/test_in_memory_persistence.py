"""LOT-07 qualification tests for in-memory persistence semantics."""

from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.schedule import (
    PersistenceVersion,
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleState,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.ports.persistence import (
    DuplicateScheduleError,
    OptimisticConcurrencyError,
    UntrackedScheduleError,
)


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _schedule(
    schedule_id: str,
    *,
    anchor_hour: int = 10,
    anchor_minute: int = 0,
) -> Schedule:
    return Schedule.create(
        schedule_id=ScheduleId(schedule_id),
        definition=ScheduleDefinition(
            target=TargetRef.python(f"app.tasks:{schedule_id}"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(anchor_hour, anchor_minute),
            ),
        ),
        reference=_instant(hour=9),
    )


def _persist(factory: InMemoryUnitOfWorkFactory, schedule: Schedule) -> None:
    with factory() as uow:
        uow.schedules.add(schedule)
        uow.commit()


def test_repository_add_does_not_commit_implicitly() -> None:
    factory = InMemoryUnitOfWorkFactory()

    with factory() as uow:
        uow.schedules.add(_schedule("schedule-1"))

        with factory() as observer:
            assert observer.schedules.get(ScheduleId("schedule-1")) is None


def test_commit_persists_schedule_round_trip() -> None:
    factory = InMemoryUnitOfWorkFactory()
    original = _schedule("schedule-1")

    _persist(factory, original)

    with factory() as uow:
        loaded = uow.schedules.get(ScheduleId("schedule-1"))

        assert loaded is not None
        assert loaded.id == original.id
        assert loaded.definition == original.definition
        assert loaded.state == original.state
        assert loaded.revision == original.revision
        assert loaded.persistence_version == original.persistence_version
        assert loaded.next_run_time == original.next_run_time
        assert loaded is not original


def test_rollback_discards_staged_insert() -> None:
    factory = InMemoryUnitOfWorkFactory()

    with factory() as uow:
        uow.schedules.add(_schedule("schedule-1"))
        uow.rollback()

    with factory() as observer:
        assert observer.schedules.get(ScheduleId("schedule-1")) is None


def test_exception_causes_rollback_on_context_exit() -> None:
    factory = InMemoryUnitOfWorkFactory()

    with pytest.raises(RuntimeError, match="boom"):
        with factory() as uow:
            uow.schedules.add(_schedule("schedule-1"))
            raise RuntimeError("boom")

    with factory() as observer:
        assert observer.schedules.get(ScheduleId("schedule-1")) is None


def test_same_unit_of_work_sees_its_staged_insert() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _schedule("schedule-1")

    with factory() as uow:
        uow.schedules.add(schedule)

        assert uow.schedules.get(schedule.id) is schedule


def test_new_unit_of_work_sees_only_committed_state() -> None:
    factory = InMemoryUnitOfWorkFactory()

    with factory() as writer:
        writer.schedules.add(_schedule("schedule-1"))

        with factory() as before_commit:
            assert before_commit.schedules.get(ScheduleId("schedule-1")) is None

        writer.commit()

        with factory() as after_commit:
            assert after_commit.schedules.get(ScheduleId("schedule-1")) is not None


def test_loaded_schedule_requires_explicit_save_to_persist_mutation() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(factory, _schedule("schedule-1"))

    with factory() as uow:
        loaded = uow.schedules.get(ScheduleId("schedule-1"))
        assert loaded is not None
        loaded.pause()
        uow.commit()

    with factory() as observer:
        reloaded = observer.schedules.get(ScheduleId("schedule-1"))
        assert reloaded is not None
        assert reloaded.state is ScheduleState.ACTIVE
        assert reloaded.persistence_version == PersistenceVersion(0)


def test_save_and_commit_persist_mutation() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(factory, _schedule("schedule-1"))

    with factory() as uow:
        loaded = uow.schedules.get(ScheduleId("schedule-1"))
        assert loaded is not None
        loaded.pause()
        uow.schedules.save(loaded)
        uow.commit()

    with factory() as observer:
        reloaded = observer.schedules.get(ScheduleId("schedule-1"))
        assert reloaded is not None
        assert reloaded.state is ScheduleState.PAUSED
        assert reloaded.persistence_version == PersistenceVersion(1)


def test_repository_identity_map_returns_same_instance_within_transaction() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(factory, _schedule("schedule-1"))

    with factory() as uow:
        first = uow.schedules.get(ScheduleId("schedule-1"))
        second = uow.schedules.get(ScheduleId("schedule-1"))

        assert first is second


def test_save_rejects_detached_schedule() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(factory, _schedule("schedule-1"))
    detached = _schedule("schedule-1")

    with factory() as uow, pytest.raises(UntrackedScheduleError):
        uow.schedules.save(detached)


def test_duplicate_schedule_id_is_rejected_at_commit() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(factory, _schedule("schedule-1"))

    with factory() as uow:
        uow.schedules.add(_schedule("schedule-1"))

        with pytest.raises(DuplicateScheduleError):
            uow.commit()


def test_stale_writer_is_rejected_by_optimistic_concurrency() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(factory, _schedule("schedule-1"))

    with factory() as first, factory() as second:
        first_loaded = first.schedules.get(ScheduleId("schedule-1"))
        second_loaded = second.schedules.get(ScheduleId("schedule-1"))
        assert first_loaded is not None
        assert second_loaded is not None

        first_loaded.pause()
        first.schedules.save(first_loaded)
        first.commit()

        second_loaded.cancel()
        second.schedules.save(second_loaded)

        with pytest.raises(OptimisticConcurrencyError):
            second.commit()

    with factory() as observer:
        committed = observer.schedules.get(ScheduleId("schedule-1"))
        assert committed is not None
        assert committed.state is ScheduleState.PAUSED
        assert committed.persistence_version == PersistenceVersion(1)


def test_conflict_validation_is_atomic_for_multiple_dirty_schedules() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(factory, _schedule("schedule-1"))
    _persist(factory, _schedule("schedule-2", anchor_minute=5))

    with factory() as stale_uow:
        stale_one = stale_uow.schedules.get(ScheduleId("schedule-1"))
        stale_two = stale_uow.schedules.get(ScheduleId("schedule-2"))
        assert stale_one is not None
        assert stale_two is not None

        with factory() as winner:
            fresh_one = winner.schedules.get(ScheduleId("schedule-1"))
            assert fresh_one is not None
            fresh_one.pause()
            winner.schedules.save(fresh_one)
            winner.commit()

        stale_one.cancel()
        stale_two.pause()
        stale_uow.schedules.save(stale_one)
        stale_uow.schedules.save(stale_two)

        with pytest.raises(OptimisticConcurrencyError):
            stale_uow.commit()

    with factory() as observer:
        schedule_one = observer.schedules.get(ScheduleId("schedule-1"))
        schedule_two = observer.schedules.get(ScheduleId("schedule-2"))
        assert schedule_one is not None
        assert schedule_two is not None
        assert schedule_one.state is ScheduleState.PAUSED
        assert schedule_two.state is ScheduleState.ACTIVE
        assert schedule_two.persistence_version == PersistenceVersion(0)


def test_list_due_filters_state_orders_deterministically_and_applies_limit() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(factory, _schedule("schedule-b", anchor_minute=0))
    _persist(factory, _schedule("schedule-a", anchor_minute=0))
    _persist(factory, _schedule("schedule-c", anchor_minute=5))

    with factory() as pause_uow:
        paused = pause_uow.schedules.get(ScheduleId("schedule-c"))
        assert paused is not None
        paused.pause()
        pause_uow.schedules.save(paused)
        pause_uow.commit()

    with factory() as uow:
        due = uow.schedules.list_due(now=_instant(hour=10), limit=2)

        assert [schedule.id.value for schedule in due] == [
            "schedule-a",
            "schedule-b",
        ]


def test_list_due_excludes_future_schedule() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(factory, _schedule("future", anchor_hour=11))

    with factory() as uow:
        assert uow.schedules.list_due(now=_instant(hour=10), limit=10) == []


def test_list_due_reads_staged_changes_from_same_transaction() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _schedule("schedule-1")

    with factory() as uow:
        uow.schedules.add(schedule)

        due = uow.schedules.list_due(now=_instant(hour=10), limit=10)

        assert due == [schedule]


def test_list_due_rejects_non_positive_limit() -> None:
    factory = InMemoryUnitOfWorkFactory()

    with factory() as uow, pytest.raises(ValueError, match="limit"):
        uow.schedules.list_due(now=_instant(hour=10), limit=0)


def test_multiple_commits_in_one_unit_of_work_refresh_expected_version() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(factory, _schedule("schedule-1"))

    with factory() as uow:
        loaded = uow.schedules.get(ScheduleId("schedule-1"))
        assert loaded is not None

        loaded.pause()
        uow.schedules.save(loaded)
        uow.commit()

        loaded.resume(reference=_instant(hour=10, minute=25))
        uow.schedules.save(loaded)
        uow.commit()

    with factory() as observer:
        committed = observer.schedules.get(ScheduleId("schedule-1"))
        assert committed is not None
        assert committed.state is ScheduleState.ACTIVE
        assert committed.next_run_time == _instant(hour=10, minute=30)
        assert committed.persistence_version == PersistenceVersion(2)
