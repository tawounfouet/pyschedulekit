"""LOT-32 SQLite retention, migration, and bounded cleanup qualification."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from pyschedulekit import (
    Duration,
    Instant,
    IntervalTrigger,
    RetentionPolicy,
    Scheduler,
    SqliteUnitOfWorkFactory,
)
from pyschedulekit.domain.outbox import OutboxMessage
from pyschedulekit.testing import MutableClock


class _Publisher:
    def publish(self, message: OutboxMessage) -> None:
        del message


def _instant() -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))


def _terminal_execution(database, clock: MutableClock) -> tuple[Scheduler, str]:
    scheduler = Scheduler(
        clock=clock,
        uow_factory=SqliteUnitOfWorkFactory(database),
    )
    scheduler.add_schedule(
        id="retention-sql",
        target=lambda: None,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant().add(Duration.minutes(10)),
        ),
    )
    clock.advance(Duration.minutes(10))
    cycle = scheduler.run_pending()
    return scheduler, cycle.executions[0].execution.id.value


def test_t_retention_sql_001_cleanup_deletes_graph_in_referential_order(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    clock = MutableClock(_instant())
    scheduler, execution_id = _terminal_execution(database, clock)
    scheduler.dispatch_outbox(_Publisher(), limit=100)
    clock.advance(Duration.days(31))

    result = scheduler.cleanup(
        RetentionPolicy.days(
            execution_history=30,
            published_outbox=30,
        ),
        limit=100,
    )

    assert result.execution_graphs_deleted == 1
    assert result.published_outbox_messages_deleted > 0

    connection = sqlite3.connect(database)
    try:
        assert connection.execute("SELECT COUNT(*) FROM schedules").fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM executions WHERE id = ?",
            (execution_id,),
        ).fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM execution_requests").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM outbox_messages").fetchone()[0] == 0
    finally:
        connection.close()


def test_t_retention_sql_002_v7_migration_backfills_completed_at(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    clock = MutableClock(_instant())
    _, execution_id = _terminal_execution(database, clock)

    connection = sqlite3.connect(database)
    try:
        connection.execute("DROP INDEX ix_executions_retention")
        connection.execute("DROP INDEX ix_execution_requests_retention")
        connection.execute("DROP INDEX ix_outbox_published")
        connection.execute("ALTER TABLE executions DROP COLUMN completed_at")
        connection.execute("UPDATE pyschedulekit_schema SET version = 7")
        connection.commit()
    finally:
        connection.close()

    SqliteUnitOfWorkFactory(database)

    connection = sqlite3.connect(database)
    try:
        version = connection.execute(
            "SELECT version FROM pyschedulekit_schema"
        ).fetchone()
        completed_at = connection.execute(
            "SELECT completed_at FROM executions WHERE id = ?",
            (execution_id,),
        ).fetchone()
        assert version is not None
        assert int(version[0]) == 8
        assert completed_at is not None
        assert completed_at[0] is not None
    finally:
        connection.close()
