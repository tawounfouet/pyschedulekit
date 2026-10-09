"""CAL-01 domain qualification for Schedule calendar binding."""

from datetime import UTC, datetime

from pyschedulekit.domain.calendar import CalendarRef, CalendarRevision, CalendarSnapshotRef
from pyschedulekit.domain.schedule import (
    PersistenceVersion,
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleRevision,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import IntervalTrigger


def _instant(*, hour: int, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _calendar(revision: int) -> CalendarSnapshotRef:
    return CalendarSnapshotRef(
        calendar_ref=CalendarRef("fr-business-days"),
        revision=CalendarRevision(revision),
    )


def _definition(calendar: CalendarSnapshotRef | None) -> ScheduleDefinition:
    return ScheduleDefinition(
        target=TargetRef.python("jobs:calendar"),
        trigger=IntervalTrigger(
            every=Duration.days(1),
            anchor=_instant(hour=10),
        ),
        calendar=calendar,
    )


def test_schedule_definition_defaults_to_no_calendar_binding() -> None:
    assert _definition(None).calendar is None


def test_calendar_binding_is_functional_definition_without_timing_semantics_yet() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("calendar-bound"),
        definition=_definition(_calendar(1)),
        reference=_instant(hour=9),
    )

    assert schedule.definition.calendar == _calendar(1)
    assert schedule.revision == ScheduleRevision(1)
    assert schedule.persistence_version == PersistenceVersion(0)
    assert schedule.next_run_time == _instant(hour=10)

    schedule.reschedule(
        definition=_definition(_calendar(2)),
        reference=_instant(hour=9, minute=30),
    )

    assert schedule.definition.calendar == _calendar(2)
    assert schedule.revision == ScheduleRevision(2)
    assert schedule.persistence_version == PersistenceVersion(1)
    assert schedule.next_run_time == _instant(hour=10)
