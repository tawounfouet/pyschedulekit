"""POST-00C qualification for concurrent SQLite schema bootstrap."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory
from pyschedulekit.infrastructure.sqlite_schema import SCHEMA_VERSION


def _assert_current_schema(database) -> None:
    connection = sqlite3.connect(database)
    try:
        row = connection.execute(
            "SELECT version FROM pyschedulekit_schema LIMIT 1"
        ).fetchone()
        assert row is not None
        assert int(row[0]) == SCHEMA_VERSION

        required_tables = {
            "schedules",
            "execution_requests",
            "executions",
            "attempts",
            "outbox_messages",
            "execution_claims",
            "schedule_admission_locks",
            "schedule_materialization_leases",
        }
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()
        tables = {str(row[0]) for row in rows}
        assert required_tables <= tables
    finally:
        connection.close()


def test_concurrent_fresh_database_bootstrap_is_atomic_and_idempotent(tmp_path) -> None:
    workers = 8

    for round_number in range(20):
        database = tmp_path / f"scheduler-{round_number}.db"
        barrier = Barrier(workers)

        def initialize(
            _: int,
            *,
            start_barrier=barrier,
            target_database=database,
        ) -> None:
            start_barrier.wait(timeout=5)
            factory = SqliteUnitOfWorkFactory(target_database)
            with factory():
                pass

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(initialize, range(workers)))

        _assert_current_schema(database)


def test_repeated_factory_initialization_reuses_current_schema(tmp_path) -> None:
    database = tmp_path / "scheduler.db"

    for _ in range(20):
        factory = SqliteUnitOfWorkFactory(database)
        with factory():
            pass

    _assert_current_schema(database)
