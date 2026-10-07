"""LOT-29 integration tests for distributed Schedule materialization coordination."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from pyschedulekit.application.materialization import ScheduleMaterializationCoordinator
from pyschedulekit.application.scheduler_engine import SchedulerEngine
from pyschedulekit.domain.claim import WorkerId
from pyschedulekit.domain.execution_request import ExecutionRequest
from pyschedulekit.domain.materialization_lease import ScheduleMaterializationLeaseState
from pyschedulekit.domain.occurrence import OccurrencePlanner
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory
from pyschedulekit.ports.persistence import OptimisticConcurrencyError


def _instant(second: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, second, tzinfo=UTC))


def _schedule(schedule_id: str) -> Schedule:
    return Schedule.create(
        schedule_id=ScheduleId(schedule_id),
        definition=ScheduleDefinition(
            target=TargetRef.python(f"jobs:{schedule_id}"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(),
            ),
        ),
        reference=Instant(datetime(2026, 1, 1, 9, 0, tzinfo=UTC)),
    )


def _persist(factory: SqliteUnitOfWorkFactory, *schedules: Schedule) -> None:
    with factory() as uow:
        for schedule in schedules:
            uow.schedules.add(schedule)
        uow.commit()


def _coordinator(
    factory: SqliteUnitOfWorkFactory,
    worker_id: str,
) -> ScheduleMaterializationCoordinator:
    return ScheduleMaterializationCoordinator(
        uow_factory=factory,
        worker_id=WorkerId(worker_id),
        ttl=Duration.seconds(5),
    )


def test_t_coord_sql_001_active_owner_denies_second_materializer(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)
    schedule = _schedule("shared")
    _persist(factory, schedule)

    holder = _coordinator(factory, "worker-a")
    held = holder.acquire(schedule_id=schedule.id, now=_instant())
    assert held.handle is not None

    contender = _coordinator(SqliteUnitOfWorkFactory(database), "worker-b")
    denied = SchedulerEngine(
        uow_factory=SqliteUnitOfWorkFactory(database),
        materialization_coordinator=contender,
    ).evaluate(evaluation_now=_instant())

    assert denied.requests == ()
    assert denied.coordination_denied_schedules == (schedule.id,)

    with factory() as uow:
        persisted = uow.schedules.get(schedule.id)
        assert persisted is not None
        assert persisted.next_run_time == _instant()

    assert holder.release(handle=held.handle, released_at=_instant(1))

    admitted = SchedulerEngine(
        uow_factory=SqliteUnitOfWorkFactory(database),
        materialization_coordinator=contender,
    ).evaluate(evaluation_now=_instant(1))

    assert len(admitted.requests) == 1
    assert admitted.coordination_denied_schedules == ()

    with factory() as uow:
        persisted = uow.schedules.get(schedule.id)
        lease = uow.materialization_leases.get(schedule.id)
        assert persisted is not None
        assert lease is not None
        assert persisted.next_run_time == Instant(datetime(2026, 1, 1, 10, 10, tzinfo=UTC))
        assert lease.state is ScheduleMaterializationLeaseState.RELEASED
        assert lease.worker_id == WorkerId("worker-b")
        assert lease.generation == held.handle.generation + 1


def test_t_coord_sql_002_different_schedules_have_independent_owners(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    first = _schedule("schedule-a")
    second = _schedule("schedule-b")
    _persist(factory, first, second)

    worker_a = _coordinator(factory, "worker-a")
    worker_b = _coordinator(factory, "worker-b")

    first_owner = worker_a.acquire(schedule_id=first.id, now=_instant())
    second_owner = worker_b.acquire(schedule_id=second.id, now=_instant())

    assert first_owner.acquired
    assert second_owner.acquired
    assert not worker_b.acquire(schedule_id=first.id, now=_instant()).acquired
    assert not worker_a.acquire(schedule_id=second.id, now=_instant()).acquired


def test_t_coord_sql_003_stale_generation_rolls_back_checkpoint_and_request(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)
    schedule = _schedule("stale")
    _persist(factory, schedule)

    owner = _coordinator(factory, "worker-a")
    acquired = owner.acquire(schedule_id=schedule.id, now=_instant())
    assert acquired.handle is not None

    stale_factory = SqliteUnitOfWorkFactory(database)
    with stale_factory() as uow:
        stale_schedule = uow.schedules.get(schedule.id)
        stale_lease = uow.materialization_leases.get(schedule.id)
        assert stale_schedule is not None
        assert stale_lease is not None

        occurrence = OccurrencePlanner().current(stale_schedule)
        assert occurrence is not None
        request = ExecutionRequest.from_occurrence(
            occurrence=occurrence,
            target=stale_schedule.definition.target,
            created_at=_instant(1),
        )
        uow.requests.add(request)
        stale_schedule.advance_next_run_after(reference=occurrence.scheduled_at)
        uow.schedules.save(stale_schedule)

        takeover = _coordinator(
            SqliteUnitOfWorkFactory(database),
            "worker-b",
        ).acquire(
            schedule_id=schedule.id,
            now=_instant(5),
        )
        assert takeover.handle is not None
        assert takeover.handle.generation == acquired.handle.generation + 1

        stale_lease.release(
            worker_id=acquired.handle.worker_id,
            token=acquired.handle.token,
            generation=acquired.handle.generation,
            released_at=_instant(1),
        )
        uow.materialization_leases.save(stale_lease)

        with pytest.raises(OptimisticConcurrencyError):
            uow.commit()

    with factory() as uow:
        persisted = uow.schedules.get(schedule.id)
        lease = uow.materialization_leases.get(schedule.id)
        occurrence = OccurrencePlanner().current(persisted) if persisted is not None else None
        assert persisted is not None
        assert lease is not None
        assert occurrence is not None
        assert persisted.next_run_time == _instant()
        assert uow.requests.get_by_occurrence(occurrence.key) is None
        assert lease.worker_id == WorkerId("worker-b")
        assert lease.generation == acquired.handle.generation + 1
        assert lease.state is ScheduleMaterializationLeaseState.ACTIVE


def test_t_coord_sql_004_v6_database_migrates_to_v7(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    SqliteUnitOfWorkFactory(database)

    connection = sqlite3.connect(database)
    try:
        connection.execute("DROP INDEX ix_schedule_materialization_leases_active")
        connection.execute("DROP TABLE schedule_materialization_leases")
                connection.execute("DROP INDEX IF EXISTS ix_executions_retention")
        connection.execute("DROP INDEX IF EXISTS ix_execution_requests_retention")
        connection.execute("DROP INDEX IF EXISTS ix_outbox_published")
        connection.execute("ALTER TABLE executions DROP COLUMN completed_at")
connection.execute("UPDATE pyschedulekit_schema SET version = 6")
        connection.commit()
    finally:
        connection.close()

    SqliteUnitOfWorkFactory(database)

    connection = sqlite3.connect(database)
    try:
        version = connection.execute("SELECT version FROM pyschedulekit_schema").fetchone()
        table = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'schedule_materialization_leases'
            """
        ).fetchone()
        assert version is not None
        assert int(version[0]) == 8
        assert table is not None
    finally:
        connection.close()
