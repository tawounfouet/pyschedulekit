"""LOT-25 end-to-end transactional outbox qualification."""

from datetime import UTC, datetime

from pyschedulekit import (
    Duration,
    IntervalTrigger,
    OutboxMessage,
    OutboxState,
    Scheduler,
    SqliteUnitOfWorkFactory,
)
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0):
    from pyschedulekit import Instant

    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


class _RecordingPublisher:
    def __init__(self) -> None:
        self.messages: list[OutboxMessage] = []

    def publish(self, message: OutboxMessage) -> None:
        self.messages.append(message)


def test_t_outbox_e2e_001_execution_lifecycle_is_published_from_durable_outbox(
    tmp_path,
) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock, uow_factory=factory)
    calls: list[str] = []

    scheduler.add_schedule(
        id="outbox-e2e",
        target=lambda: calls.append("ran"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )

    clock.advance(Duration.minutes(10))
    result = scheduler.run_pending()

    assert calls == ["ran"]
    assert len(result.executions) == 1

    with factory() as uow:
        pending = uow.outbox.list_pending(limit=10)

    assert [message.event_type for message in pending] == [
        "execution.attempt.started",
        "execution.attempt.completed",
    ]
    assert all(message.state is OutboxState.PENDING for message in pending)

    publisher = _RecordingPublisher()
    dispatch = scheduler.dispatch_outbox(publisher)

    assert dispatch.published == 2
    assert dispatch.failed == 0
    assert [message.event_type for message in publisher.messages] == [
        "execution.attempt.started",
        "execution.attempt.completed",
    ]

    with factory() as uow:
        assert uow.outbox.list_pending(limit=10) == ()
