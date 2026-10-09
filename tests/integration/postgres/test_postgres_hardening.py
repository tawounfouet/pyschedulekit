"""PG-05 PostgreSQL production-hardening qualification."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any, cast

import psycopg
import pytest
from psycopg import IsolationLevel
from psycopg.errors import DeadlockDetected, SerializationFailure

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
