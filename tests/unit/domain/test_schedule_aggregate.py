"""LOT-05 qualification tests for the Schedule aggregate."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.schedule import (
    InvalidScheduleOperationError,
    InvalidScheduleTransitionError,
    PersistenceVersion,
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleRevision,
    ScheduleState,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant, Timezone
from pyschedulekit.domain.triggers import DateTrigger, IntervalTrigger


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _interval_definition(
    *,
    anchor: Instant | None = None,
    every: Duration | None = None,
    timezone: Timezone | None = None,
) -> ScheduleDefinition:
    return ScheduleDefinition(
        target=TargetRef.python("app.tasks:refresh"),
        trigger=IntervalTrigger(
            every=every or Duration.minutes(10),
            anchor=anchor or _instant(),
        ),
        timezone=timezone or Timezone("UTC"),
    )


def test_t_sch_001_create_valid_schedule() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=_interval_definition(),
        reference=_instant(hour=9),
    )

    assert schedule.id == ScheduleId("schedule-1")
    assert schedule.state is ScheduleState.ACTIVE
    assert schedule.revision == ScheduleRevision(1)
    assert schedule.persistence_version == PersistenceVersion(0)
    assert schedule.next_run_time == _instant(hour=10)


def test_create_with_exhausted_trigger_is_immediately_completed() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=ScheduleDefinition(
            target=TargetRef.python("app.tasks:once"),
            trigger=DateTrigger(at=_instant(hour=10)),
        ),
        reference=_instant(hour=10),
    )

    assert schedule.state is ScheduleState.COMPLETED
    assert schedule.next_run_time is None


def test_t_sch_002_pause_active_schedule() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=_interval_definition(),
        reference=_instant(hour=9),
    )

    schedule.pause()

    assert schedule.state is ScheduleState.PAUSED
    assert schedule.next_run_time is None
    assert schedule.persistence_version == PersistenceVersion(1)


def test_t_sch_003_pause_is_idempotent() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=_interval_definition(),
        reference=_instant(hour=9),
    )

    schedule.pause()
    version_after_first_pause = schedule.persistence_version
    schedule.pause()

    assert schedule.state is ScheduleState.PAUSED
    assert schedule.persistence_version == version_after_first_pause


def test_t_sch_004_resume_recalculates_from_resume_reference() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=_interval_definition(),
        reference=_instant(hour=9),
    )
    schedule.pause()

    schedule.resume(reference=_instant(hour=10, minute=25))

    assert schedule.state is ScheduleState.ACTIVE
    assert schedule.next_run_time == _instant(hour=10, minute=30)
    assert schedule.persistence_version == PersistenceVersion(2)


def test_t_sch_005_resume_cancelled_schedule_is_rejected() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=_interval_definition(),
        reference=_instant(hour=9),
    )
    schedule.cancel()

    with pytest.raises(InvalidScheduleTransitionError):
        schedule.resume(reference=_instant(hour=11))


def test_t_sch_006_cancel_active_schedule() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=_interval_definition(),
        reference=_instant(hour=9),
    )

    schedule.cancel()

    assert schedule.state is ScheduleState.CANCELLED
    assert schedule.next_run_time is None
    assert schedule.persistence_version == PersistenceVersion(1)


def test_t_sch_007_cancel_is_idempotent() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=_interval_definition(),
        reference=_instant(hour=9),
    )

    schedule.cancel()
    version_after_first_cancel = schedule.persistence_version
    schedule.cancel()

    assert schedule.persistence_version == version_after_first_cancel


def test_t_sch_008_trigger_exhaustion_completes_schedule() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=ScheduleDefinition(
            target=TargetRef.python("app.tasks:once"),
            trigger=DateTrigger(at=_instant(hour=10)),
        ),
        reference=_instant(hour=9),
    )

    next_run_time = schedule.advance_next_run_after(reference=_instant(hour=10))

    assert next_run_time is None
    assert schedule.state is ScheduleState.COMPLETED
    assert schedule.next_run_time is None


def test_t_sch_009_reschedule_increments_revision() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=_interval_definition(),
        reference=_instant(hour=9),
    )
    new_definition = _interval_definition(every=Duration.minutes(30))

    schedule.reschedule(
        definition=new_definition,
        reference=_instant(hour=10),
    )

    assert schedule.revision == ScheduleRevision(2)
    assert schedule.definition == new_definition
    assert schedule.next_run_time == _instant(hour=10, minute=30)


def test_t_sch_010_operational_checkpoint_does_not_increment_revision() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=_interval_definition(),
        reference=_instant(hour=9),
    )
    revision = schedule.revision
    persistence_version = schedule.persistence_version

    schedule.advance_next_run_after(reference=_instant(hour=10))

    assert schedule.revision == revision
    assert schedule.persistence_version == persistence_version.next()
    assert schedule.next_run_time == _instant(hour=10, minute=10)


def test_t_sch_011_reschedule_preserves_schedule_identity() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=_interval_definition(),
        reference=_instant(hour=9),
    )

    schedule.reschedule(
        definition=_interval_definition(every=Duration.minutes(30)),
        reference=_instant(hour=10),
    )

    assert schedule.id == ScheduleId("schedule-1")


def test_reschedule_paused_schedule_changes_definition_but_stays_paused() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=_interval_definition(),
        reference=_instant(hour=9),
    )
    schedule.pause()

    schedule.reschedule(
        definition=_interval_definition(every=Duration.minutes(30)),
        reference=_instant(hour=10),
    )

    assert schedule.state is ScheduleState.PAUSED
    assert schedule.next_run_time is None
    assert schedule.revision == ScheduleRevision(2)


def test_terminal_schedule_cannot_be_rescheduled() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=_interval_definition(),
        reference=_instant(hour=9),
    )
    schedule.cancel()

    with pytest.raises(InvalidScheduleTransitionError):
        schedule.reschedule(
            definition=_interval_definition(every=Duration.minutes(30)),
            reference=_instant(hour=10),
        )


def test_advance_rejects_reference_before_current_checkpoint() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=_interval_definition(),
        reference=_instant(hour=9),
    )

    with pytest.raises(InvalidScheduleOperationError):
        schedule.advance_next_run_after(reference=_instant(hour=9, minute=30))


def test_t_sch_015_effective_timezone_is_frozen_in_definition() -> None:
    scheduler_default = Timezone("Europe/Paris")
    definition = _interval_definition(timezone=scheduler_default)
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=definition,
        reference=_instant(hour=9),
    )

    scheduler_default = Timezone("America/New_York")

    assert scheduler_default.name == "America/New_York"
    assert schedule.definition.timezone.name == "Europe/Paris"


def test_schedule_definition_is_immutable() -> None:
    definition = _interval_definition()

    with pytest.raises(FrozenInstanceError):
        definition.timezone = Timezone("Europe/Paris")  # type: ignore[misc]


def test_target_ref_is_declarative_and_immutable() -> None:
    target = TargetRef.python("app.tasks:refresh")

    assert target.kind == "python"
    assert target.reference == "app.tasks:refresh"

    with pytest.raises(FrozenInstanceError):
        target.reference = "other"  # type: ignore[misc]


def test_revision_and_persistence_version_are_distinct_value_objects() -> None:
    revision = ScheduleRevision()
    persistence_version = PersistenceVersion()

    assert revision.next() == ScheduleRevision(2)
    assert persistence_version.next() == PersistenceVersion(1)
