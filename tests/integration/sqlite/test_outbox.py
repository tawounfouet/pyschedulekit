"""LOT-25 integration tests for transactional outbox persistence."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from pyschedulekit.application.outbox import OutboxDispatcher, make_outbox_message
from pyschedulekit.domain.outbox import OutboxMessage, OutboxState
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory
from pyschedulekit.ports.persistence import DuplicateOutboxMessageError
from pyschedulekit.testing import MutableClock


def _instant(minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, minute, tzinfo=UTC))


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


class _RecordingPublisher:
    def __init__(self) -> None:
        self.messages: list[OutboxMessage] = []

    def publish(self, message: OutboxMessage) -> None:
        self.messages.append(message)


class _FailOncePublisher:
    def __init__(self) -> None:
        self.calls = 0
        self.messages: list[OutboxMessage] = []

    def publish(self, message: OutboxMessage) -> None:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("broker unavailable")
        self.messages.append(message)


def test_t_outbox_sql_001_repository_round_trip(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    message = make_outbox_message(
        event_type="execution.test",
        aggregate_type="execution",
        aggregate_id="execution-1",
        created_at=_instant(),
        payload={"value": "1"},
    )

    with factory() as uow:
        uow.outbox.add(message)
        uow.commit()

    with factory() as uow:
        loaded = uow.outbox.get(message.id)
        pending = uow.outbox.list_pending(limit=10)

        assert loaded is not None
        assert loaded.event_type == "execution.test"
        assert loaded.payload == (("value", "1"),)
        assert loaded.state is OutboxState.PENDING
        assert [item.id for item in pending] == [message.id]


def test_t_outbox_sql_002_duplicate_outbox_rolls_back_business_write(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    message = make_outbox_message(
        event_type="execution.test",
        aggregate_type="execution",
        aggregate_id="execution-1",
        created_at=_instant(),
        payload={},
    )

    with factory() as uow:
        uow.outbox.add(message)
        uow.commit()

    with factory() as uow:
        uow.schedules.add(_schedule("must-rollback"))
        uow.outbox.add(
            make_outbox_message(
                event_type="execution.test",
                aggregate_type="execution",
                aggregate_id="execution-1",
                created_at=_instant(minute=1),
                payload={},
            )
        )
        with pytest.raises(DuplicateOutboxMessageError):
            uow.commit()

    with factory() as observer:
        assert observer.schedules.get(ScheduleId("must-rollback")) is None


def test_t_outbox_sql_003_dispatch_marks_message_published(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    message = make_outbox_message(
        event_type="execution.test",
        aggregate_type="execution",
        aggregate_id="execution-1",
        created_at=_instant(),
        payload={},
    )
    with factory() as uow:
        uow.outbox.add(message)
        uow.commit()

    publisher = _RecordingPublisher()
    result = OutboxDispatcher(
        clock=MutableClock(_instant(minute=1)),
        uow_factory=factory,
        publisher=publisher,
    ).dispatch_pending()

    assert result.published_message_ids == (message.id,)
    assert result.failed_message_ids == ()
    assert [item.id for item in publisher.messages] == [message.id]

    with factory() as uow:
        stored = uow.outbox.get(message.id)
        assert stored is not None
        assert stored.state is OutboxState.PUBLISHED
        assert stored.publish_attempts == 1
        assert stored.published_at == _instant(minute=1)


def test_t_outbox_sql_004_failed_publish_remains_pending_then_retries(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    message = make_outbox_message(
        event_type="execution.test",
        aggregate_type="execution",
        aggregate_id="execution-1",
        created_at=_instant(),
        payload={},
    )
    with factory() as uow:
        uow.outbox.add(message)
        uow.commit()

    publisher = _FailOncePublisher()
    dispatcher = OutboxDispatcher(
        clock=MutableClock(_instant(minute=1)),
        uow_factory=factory,
        publisher=publisher,
    )

    first = dispatcher.dispatch_pending()
    second = dispatcher.dispatch_pending()

    assert first.failed_message_ids == (message.id,)
    assert second.published_message_ids == (message.id,)
    assert publisher.calls == 2

    with factory() as uow:
        stored = uow.outbox.get(message.id)
        assert stored is not None
        assert stored.state is OutboxState.PUBLISHED
        assert stored.publish_attempts == 2
        assert stored.last_error is None


def test_t_outbox_sql_005_pending_messages_are_oldest_first(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    late = make_outbox_message(
        event_type="late",
        aggregate_type="execution",
        aggregate_id="late",
        created_at=_instant(minute=2),
        payload={},
    )
    early = make_outbox_message(
        event_type="early",
        aggregate_type="execution",
        aggregate_id="early",
        created_at=_instant(),
        payload={},
    )

    with factory() as uow:
        uow.outbox.add(late)
        uow.outbox.add(early)
        uow.commit()

    with factory() as uow:
        pending = uow.outbox.list_pending(limit=10)

    assert [item.id for item in pending] == [early.id, late.id]


def test_t_outbox_sql_006_v2_database_migrates_through_current_schema(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    SqliteUnitOfWorkFactory(database)

    connection = sqlite3.connect(database)
    try:
        connection.execute("DROP INDEX ix_schedule_materialization_leases_active")
        connection.execute("DROP TABLE schedule_materialization_leases")
        connection.execute("DROP INDEX ix_schedule_admission_locks_active")
        connection.execute("DROP TABLE schedule_admission_locks")
        connection.execute("DROP INDEX ix_execution_claims_active")
        connection.execute("DROP TABLE execution_claims")
        connection.execute("DROP INDEX ix_outbox_pending")
        connection.execute("DROP TABLE outbox_messages")
        connection.execute("DROP INDEX IF EXISTS ix_executions_retention")
        connection.execute("DROP INDEX IF EXISTS ix_execution_requests_retention")
        connection.execute("DROP INDEX IF EXISTS ix_outbox_published")
        connection.execute("ALTER TABLE executions DROP COLUMN completed_at")
        connection.execute("UPDATE pyschedulekit_schema SET version = 2")
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
            WHERE type = 'table' AND name = 'outbox_messages'
            """
        ).fetchone()

        assert version is not None
        assert int(version[0]) == 8
        assert table is not None
    finally:
        connection.close()
