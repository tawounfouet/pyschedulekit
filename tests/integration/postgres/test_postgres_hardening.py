"""PG-05 PostgreSQL production-hardening qualification."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any, cast

import psycopg
import pytest
from benchmarks.run import _postgres_cycle_sample
from psycopg import IsolationLevel
from psycopg.errors import DeadlockDetected, SerializationFailure
from psycopg.rows import dict_row
from pyschedulekit.domain.schedule import ScheduleId
from pyschedulekit.infrastructure.postgres import (
    PostgresUnitOfWork,
    PostgresUnitOfWorkFactory,
    _ordered_ids,
)
from pyschedulekit.ports.persistence import TransientPersistenceError

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


def _factory() -> PostgresUnitOfWorkFactory:
    assert POSTGRES_DSN is not None
    return PostgresUnitOfWorkFactory(POSTGRES_DSN)


def test_pg05_write_set_identity_order_is_deterministic() -> None:
    ordered = _ordered_ids(
        {
            ScheduleId("schedule-z"),
            ScheduleId("schedule-a"),
            ScheduleId("schedule-m"),
        }
    )

    assert [item.value for item in ordered] == [
        "schedule-a",
        "schedule-m",
        "schedule-z",
    ]


def test_pg05_unit_of_work_uses_read_committed_and_closes_connection() -> None:
    factory = _factory()
    uow = cast(PostgresUnitOfWork, factory())
    connection = uow._connection

    assert connection.isolation_level is IsolationLevel.READ_COMMITTED
    assert connection.closed is False

    with uow:
        assert connection.closed is False

    assert connection.closed is True


class _FailingCommitConnection:
    def __init__(self, error: Exception) -> None:
        self._error = error
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0

    def commit(self) -> None:
        self.commit_calls += 1
        raise self._error

    def rollback(self) -> None:
        self.rollback_calls += 1

    def close(self) -> None:
        self.close_calls += 1


@pytest.mark.parametrize(
    "database_error",
    (
        DeadlockDetected("forced deadlock"),
        SerializationFailure("forced serialization failure"),
    ),
)
def test_pg05_transient_database_abort_is_not_replayed_implicitly(
    database_error: Exception,
) -> None:
    connection = _FailingCommitConnection(database_error)
    uow = PostgresUnitOfWork(cast(Any, connection))

    uow.__enter__()
    with pytest.raises(TransientPersistenceError, match="fresh UnitOfWork"):
        uow.commit()

    assert connection.commit_calls == 1
    assert connection.rollback_calls == 1

    uow.__exit__(None, None, None)
    assert connection.close_calls == 1



def test_pg05_pool_style_provider_returns_connection_through_releaser() -> None:
    assert POSTGRES_DSN is not None
    acquired: list[psycopg.Connection[dict[str, Any]]] = []
    released: list[psycopg.Connection[dict[str, Any]]] = []

    def acquire() -> psycopg.Connection[dict[str, Any]]:
        connection = psycopg.connect(POSTGRES_DSN, row_factory=dict_row)
        acquired.append(connection)
        return connection

    def release(connection: psycopg.Connection[dict[str, Any]]) -> None:
        released.append(connection)

    factory = PostgresUnitOfWorkFactory(
        POSTGRES_DSN,
        connection_provider=acquire,
        connection_releaser=release,
    )

    with factory() as uow:
        assert uow.schedules.next_run_time() is None

    assert len(acquired) == 1
    assert released == acquired
    assert acquired[0].closed is False
    assert acquired[0].info.transaction_status.name == "IDLE"

    acquired[0].close()


def test_pg05_releaser_without_provider_is_rejected() -> None:
    assert POSTGRES_DSN is not None

    with pytest.raises(ValueError, match="requires connection_provider"):
        PostgresUnitOfWorkFactory(
            POSTGRES_DSN,
            connection_releaser=lambda connection: connection.close(),
        )


def test_pg05_postgres_benchmark_smoke_sample_executes() -> None:
    assert POSTGRES_DSN is not None

    elapsed = _postgres_cycle_sample(2, POSTGRES_DSN)

    assert elapsed >= 0
