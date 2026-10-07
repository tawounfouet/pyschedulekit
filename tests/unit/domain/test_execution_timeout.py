"""LOT-16 unit tests for execution timeout configuration."""

from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.execution import ExecutionPolicySnapshot
from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.schedule import (
    ScheduleDefinition,
    ScheduleId,
    ScheduleRevision,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import IntervalTrigger


def _instant() -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))


def test_t_timeout_001_schedule_accepts_positive_timeout() -> None:
    definition = ScheduleDefinition(
        target=TargetRef.python("job"),
        trigger=IntervalTrigger(
            every=Duration.minutes(5),
            anchor=_instant(),
        ),
        timeout=Duration.seconds(30),
    )

    assert definition.timeout == Duration.seconds(30)


def test_t_timeout_002_schedule_rejects_zero_timeout() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        ScheduleDefinition(
            target=TargetRef.python("job"),
            trigger=IntervalTrigger(
                every=Duration.minutes(5),
                anchor=_instant(),
            ),
            timeout=Duration.seconds(0),
        )


def test_t_timeout_003_execution_request_rejects_zero_timeout() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        ExecutionRequest(
            id=RequestId("request-timeout"),
            occurrence_key=OccurrenceKey(
                schedule_id=ScheduleId("schedule-timeout"),
                schedule_revision=ScheduleRevision(1),
                scheduled_at=_instant(),
            ),
            target=TargetRef.python("job"),
            created_at=_instant(),
            timeout=Duration.seconds(0),
        )


def test_t_timeout_004_execution_snapshot_rejects_zero_timeout() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        ExecutionPolicySnapshot(timeout=Duration.seconds(0))
