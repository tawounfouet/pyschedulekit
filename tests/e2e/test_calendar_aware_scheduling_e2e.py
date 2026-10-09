"""CAL-02 end-to-end qualification through the public Scheduler facade."""

from datetime import UTC, datetime

import pytest

from pyschedulekit import (
    BusinessCalendar,
    CalendarRef,
    CalendarRevision,
    CalendarSnapshotRef,
    Duration,
    InMemoryCalendarProvider,
    Instant,
    IntervalTrigger,
    PyScheduleKitConfigurationError,
    Scheduler,
)
from pyschedulekit.testing import MutableClock


def _instant(day: int, hour: int = 10) -> Instant:
    return Instant(datetime(2026, 1, day, hour, tzinfo=UTC))


def _calendar() -> BusinessCalendar:
    return BusinessCalendar(
        calendar_ref=CalendarRef("business-days"),
        revision=CalendarRevision(1),
    )


def test_scheduler_skips_weekend_between_public_run_pending_cycles() -> None:
    calendar = _calendar()
    clock = MutableClock(_instant(2, hour=9))
    executions: list[str] = []
    scheduler = Scheduler(
        clock=clock,
        calendar_provider=InMemoryCalendarProvider([calendar]),
    )

    schedule_id = scheduler.add_schedule(
        id="business-daily",
        target=lambda: executions.append("ran"),
        trigger=IntervalTrigger(
            every=Duration.days(1),
            anchor=_instant(2),
        ),
        calendar=calendar.snapshot_ref,
    )

    assert scheduler.inspect_schedule(schedule_id).next_run_time == _instant(2)

    clock.set(_instant(2))
    friday = scheduler.run_pending()
    assert len(friday.executions) == 1
    assert executions == ["ran"]
    assert scheduler.inspect_schedule(schedule_id).next_run_time == _instant(5)

    clock.set(_instant(3))
    saturday = scheduler.run_pending()
    assert saturday.executions == ()
    assert executions == ["ran"]

    clock.set(_instant(5))
    monday = scheduler.run_pending()
    assert len(monday.executions) == 1
    assert executions == ["ran", "ran"]
    assert scheduler.inspect_schedule(schedule_id).next_run_time == _instant(6)


def test_calendar_bound_schedule_fails_closed_when_revision_is_not_registered() -> None:
    scheduler = Scheduler(clock=MutableClock(_instant(2, hour=9)))
    binding = CalendarSnapshotRef(
        calendar_ref=CalendarRef("business-days"),
        revision=CalendarRevision(1),
    )

    with pytest.raises(PyScheduleKitConfigurationError, match="not registered"):
        scheduler.add_schedule(
            id="missing-calendar",
            target=lambda: None,
            trigger=IntervalTrigger(
                every=Duration.days(1),
                anchor=_instant(2),
            ),
            calendar=binding,
        )
