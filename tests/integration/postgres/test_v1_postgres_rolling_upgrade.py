"""V1-02.E PostgreSQL evolution and same-contract rolling-overlap qualification."""

from __future__ import annotations

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier

import psycopg
import pytest

from pyschedulekit.application.materialization import ScheduleMaterializationCoordinator
from pyschedulekit.domain.claim import WorkerId
from pyschedulekit.domain.materialization_lease import ScheduleMaterializationLeaseState
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleState,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure.postgres import PostgresUnitOfWorkFactory
from pyschedulekit.infrastructure.persistence_versions import POSTGRES_RUNTIME_SCHEMA_VERSION

POSTGRES_DSN = os.getenv("PYSCHEDULEKIT_TEST_POSTGRES_DSN")

pytestmark = pytest.mark.postgres


@pytest.fixture(autouse=True)
def clean_postgres_schema() -> Iterator[None]:
    if POSTGRES_DSN is None:
        pytest.skip("PYSCHEDULEKIT_TEST_POSTGRES_DSN is not configured.")

    with psycopg.connect(POSTGRES_DSN, autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")

    yield

    with psycopg.connect(POSTGRES_DSN, autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")


def _instant(*, hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _factory() -> PostgresUnitOfWorkFactory:
    assert POSTGRES_DSN is not None
    return PostgresUnitOfWorkFactory(POSTGRES_DSN)


def _schedule(schedule_id: str) -> Schedule:
    return Schedule.create(
        schedule_id=ScheduleId(schedule_id),
        definition=ScheduleDefinition(
            target=TargetRef.python(f"jobs:{schedule_id}"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(minute=10),
            ),
        ),
        reference=_instant(hour=9),
    )


def test_v1_02e_concurrent_schema_v1_bootstrap_is_serialized() -> None:
    assert POSTGRES_DSN is not None
    workers = 4
    barrier = Barrier(workers)

    def bootstrap(_: int) -> bool:
        barrier.wait(timeout=10)
        PostgresUnitOfWorkFactory(POSTGRES_DSN)
        return True

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = tuple(executor.map(bootstrap, range(workers)))

    assert results == (True,) * workers

    with psycopg.connect(POSTGRES_DSN) as connection:
        versions = connection.execute(
            "SELECT version FROM pyschedulekit_schema ORDER BY version"
        ).fetchall()
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = current_schema()
                  AND table_name LIKE 'pyschedulekit_%'
                   OR table_schema = current_schema()
                      AND table_name IN (
                          'schedules',
                          'execution_requests',
                          'executions',
                          'attempts',
                          'outbox_messages',
                          'execution_claims',
                          'schedule_admission_locks',
                          'schedule_materialization_leases'
                      )
                """
            ).fetchall()
        }

    assert versions == [(POSTGRES_RUNTIME_SCHEMA_VERSION,)]
    assert {
        "pyschedulekit_schema",
        "schedules",
        "execution_requests",
        "executions",
        "attempts",
        "outbox_messages",
        "execution_claims",
        "schedule_admission_locks",
        "schedule_materialization_leases",
    } <= tables


def test_v1_02e_same_contract_workers_read_and_write_each_others_state() -> None:
    first = _factory()
    second = _factory()
    schedule = _schedule("rolling-overlap")

    with first() as uow:
        uow.schedules.add(schedule)
        uow.commit()

    with second() as uow:
        loaded = uow.schedules.get(schedule.id)
        assert loaded is not None
        assert loaded.state is ScheduleState.ACTIVE
        loaded.pause()
        uow.schedules.save(loaded)
        uow.commit()

    with first() as uow:
        reloaded = uow.schedules.get(schedule.id)
        assert reloaded is not None
        assert reloaded.state is ScheduleState.PAUSED
        assert reloaded.next_run_time is None


def test_v1_02e_same_contract_takeover_advances_fencing_and_rejects_stale_owner() -> None:
    first = _factory()
    second = _factory()
    schedule = _schedule("rolling-fencing")

    with first() as uow:
        uow.schedules.add(schedule)
        uow.commit()

    old_worker = ScheduleMaterializationCoordinator(
        uow_factory=first,
        worker_id=WorkerId("worker-old"),
        ttl=Duration.minutes(5),
    )
    new_worker = ScheduleMaterializationCoordinator(
        uow_factory=second,
        worker_id=WorkerId("worker-new"),
        ttl=Duration.minutes(5),
    )

    old = old_worker.acquire(schedule_id=schedule.id, now=_instant())
    assert old.acquired is True
    assert old.handle is not None
    assert old.handle.generation == 1

    blocked = new_worker.acquire(schedule_id=schedule.id, now=_instant(minute=1))
    assert blocked.acquired is False
    assert blocked.reason == "already_owned"

    takeover = new_worker.acquire(schedule_id=schedule.id, now=_instant(minute=6))
    assert takeover.acquired is True
    assert takeover.handle is not None
    assert takeover.handle.generation == 2

    assert old_worker.release(handle=old.handle, released_at=_instant(minute=7)) is False
    assert new_worker.release(handle=takeover.handle, released_at=_instant(minute=7)) is True

    with first() as uow:
        persisted = uow.materialization_leases.get(schedule.id)
        assert persisted is not None
        assert persisted.worker_id == WorkerId("worker-new")
        assert persisted.generation == 2
        assert persisted.state is ScheduleMaterializationLeaseState.RELEASED


def test_v1_02e_unknown_future_schema_fails_closed_without_data_mutation() -> None:
    assert POSTGRES_DSN is not None
    factory = _factory()
    schedule = _schedule("future-schema-guard")

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.commit()

    with psycopg.connect(POSTGRES_DSN, autocommit=True) as connection:
        connection.execute(
            "UPDATE pyschedulekit_schema SET version = %s",
            (POSTGRES_RUNTIME_SCHEMA_VERSION + 1,),
        )

    with pytest.raises(
        RuntimeError,
        match="Unsupported PyScheduleKit PostgreSQL schema version",
    ):
        PostgresUnitOfWorkFactory(POSTGRES_DSN)

    with psycopg.connect(POSTGRES_DSN) as connection:
        version = connection.execute("SELECT version FROM pyschedulekit_schema").fetchone()
        persisted = connection.execute(
            "SELECT state, revision, persistence_version FROM schedules WHERE id = %s",
            (schedule.id.value,),
        ).fetchone()

    assert version == (POSTGRES_RUNTIME_SCHEMA_VERSION + 1,)
    assert persisted == ("active", 1, 0)
