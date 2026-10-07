"""LOT-25 unit tests for outbox message semantics."""

from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.outbox import OutboxMessage, OutboxMessageId, OutboxState
from pyschedulekit.domain.time import Instant


def _instant(minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, minute, tzinfo=UTC))


def test_t_outbox_unit_001_message_identity_is_deterministic() -> None:
    first = OutboxMessage.create(
        event_type="execution.attempt.started",
        aggregate_type="attempt",
        aggregate_id="attempt-1",
        payload=(("execution_id", "execution-1"),),
        created_at=_instant(),
    )
    second = OutboxMessage.create(
        event_type="execution.attempt.started",
        aggregate_type="attempt",
        aggregate_id="attempt-1",
        payload=(("execution_id", "execution-1"),),
        created_at=_instant(minute=1),
    )

    assert first.id == second.id


def test_t_outbox_unit_002_different_event_type_has_different_identity() -> None:
    started = OutboxMessageId.deterministic(
        event_type="execution.attempt.started",
        aggregate_type="attempt",
        aggregate_id="attempt-1",
    )
    completed = OutboxMessageId.deterministic(
        event_type="execution.attempt.completed",
        aggregate_type="attempt",
        aggregate_id="attempt-1",
    )

    assert started != completed


def test_t_outbox_unit_003_publish_success_is_terminal() -> None:
    message = OutboxMessage.create(
        event_type="event",
        aggregate_type="execution",
        aggregate_id="execution-1",
        payload=(),
        created_at=_instant(),
    )

    message.mark_published(published_at=_instant(minute=1))

    assert message.state is OutboxState.PUBLISHED
    assert message.publish_attempts == 1
    assert message.published_at == _instant(minute=1)
    assert message.last_error is None


def test_t_outbox_unit_004_failure_keeps_message_pending() -> None:
    message = OutboxMessage.create(
        event_type="event",
        aggregate_type="execution",
        aggregate_id="execution-1",
        payload=(),
        created_at=_instant(),
    )

    message.record_failure(error="broker unavailable")

    assert message.state is OutboxState.PENDING
    assert message.publish_attempts == 1
    assert message.last_error == "broker unavailable"


def test_t_outbox_unit_005_published_message_rejects_failure_recording() -> None:
    message = OutboxMessage.create(
        event_type="event",
        aggregate_type="execution",
        aggregate_id="execution-1",
        payload=(),
        created_at=_instant(),
    )
    message.mark_published(published_at=_instant(minute=1))

    with pytest.raises(ValueError):
        message.record_failure(error="late failure")
