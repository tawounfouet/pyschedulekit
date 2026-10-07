"""LOT-32 end-to-end retention qualification through Scheduler."""

from datetime import UTC, datetime

import pytest

from pyschedulekit import (
    Duration,
    ExecutionNotFoundError,
    Instant,
    IntervalTrigger,
    RetentionPolicy,
    Scheduler,
)
from pyschedulekit.domain.outbox import OutboxMessage
from pyschedulekit.testing import MutableClock


class _RecordingPublisher:
    def __init__(self) -> None:
        self.messages: list[OutboxMessage] = []

    def publish(self, message: OutboxMessage) -> None:
        self.messages.append(message)


def _instant() -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))


def test_t_retention_e2e_001_terminal_graph_and_published_outbox_are_cleaned() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    publisher = _RecordingPublisher()

    schedule_id = scheduler.add_schedule(
        id="retained",
        target=lambda: None,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant().add(Duration.minutes(10)),
        ),
    )

    clock.advance(Duration.minutes(10))
    cycle = scheduler.run_pending()
    execution_id = cycle.executions[0].execution.id

    dispatch = scheduler.dispatch_outbox(publisher, limit=100)
    assert dispatch.published > 0

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
    assert result.total_deleted >= 2
    assert scheduler.inspect_schedule(schedule_id).schedule_id == schedule_id
    with pytest.raises(ExecutionNotFoundError):
        scheduler.inspect_execution(execution_id)


def test_t_retention_e2e_002_pending_outbox_is_never_deleted() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)

    scheduler.add_schedule(
        id="pending-outbox",
        target=lambda: None,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant().add(Duration.minutes(10)),
        ),
    )
    clock.advance(Duration.minutes(10))
    scheduler.run_pending()
    clock.advance(Duration.days(31))

    result = scheduler.cleanup(
        RetentionPolicy.days(
            execution_history=30,
            published_outbox=0,
        ),
        limit=100,
    )

    assert result.execution_graphs_deleted == 1
    assert result.published_outbox_messages_deleted == 0
