"""PG-00 integration qualification for PostgreSQL schema bootstrap."""

from __future__ import annotations

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from pyschedulekit.infrastructure.postgres_schema import (
    SCHEMA_VERSION,
    initialize_postgres_schema,
)

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


def _initialize_once() -> None:
    assert POSTGRES_DSN is not None
    with psycopg.connect(POSTGRES_DSN, autocommit=True) as connection:
        initialize_postgres_schema(connection)


def test_postgres_bootstrap_creates_current_relational_surface() -> None:
    _initialize_once()

    assert POSTGRES_DSN is not None
    with psycopg.connect(POSTGRES_DSN, autocommit=True) as connection:
        version = connection.execute(
            "SELECT version FROM pyschedulekit_schema"
        ).fetchone()
        tables = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                """
            ).fetchall()
        }

    assert version == (SCHEMA_VERSION,)
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


def test_postgres_bootstrap_is_idempotent() -> None:
    _initialize_once()
    _initialize_once()

    assert POSTGRES_DSN is not None
    with psycopg.connect(POSTGRES_DSN, autocommit=True) as connection:
        rows = connection.execute(
            "SELECT singleton, version FROM pyschedulekit_schema"
        ).fetchall()

    assert rows == [(True, SCHEMA_VERSION)]


def test_postgres_bootstrap_is_concurrency_safe() -> None:
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_initialize_once) for _ in range(8)]
        for future in futures:
            future.result()

    assert POSTGRES_DSN is not None
    with psycopg.connect(POSTGRES_DSN, autocommit=True) as connection:
        count = connection.execute(
            "SELECT count(*) FROM pyschedulekit_schema"
        ).fetchone()

    assert count == (1,)


def test_postgres_bootstrap_fails_closed_on_unknown_schema_version() -> None:
    _initialize_once()

    assert POSTGRES_DSN is not None
    with psycopg.connect(POSTGRES_DSN, autocommit=True) as connection:
        connection.execute("UPDATE pyschedulekit_schema SET version = 999")

        with pytest.raises(
            RuntimeError,
            match="Unsupported PyScheduleKit PostgreSQL schema version",
        ):
            initialize_postgres_schema(connection)


def test_postgres_temporal_columns_are_native_timestamptz() -> None:
    _initialize_once()

    assert POSTGRES_DSN is not None
    with psycopg.connect(POSTGRES_DSN, autocommit=True) as connection:
        temporal_columns = {
            (str(row[0]), str(row[1]))
            for row in connection.execute(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND data_type = 'timestamp with time zone'
                """
            ).fetchall()
        }

    assert ("schedules", "next_run_time") in temporal_columns
    assert ("execution_requests", "scheduled_at") in temporal_columns
    assert ("executions", "next_attempt_at") in temporal_columns
    assert ("executions", "completed_at") in temporal_columns
    assert ("execution_claims", "expires_at") in temporal_columns
    assert ("schedule_materialization_leases", "expires_at") in temporal_columns
