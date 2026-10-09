"""CAL-03 end-to-end qualification for BusinessDayTrigger."""

from datetime import UTC, date, datetime

import pytest

from pyschedulekit import (
    BusinessCalendar,
    BusinessDayTrigger,
    CalendarRef,
    CalendarRevision,
    InMemoryCalendarProvider,
    Instant,
    PyScheduleKitConfigurationError,
    Scheduler,
    Timezone,
)
from pyschedulekit.testing import MutableClock


def _instant(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> Instant:
    return Instant(datetime(year, month, day, hour, minute, tzinfo=UTC))


def _calendar() -> BusinessCalendar:
    return BusinessCalendar(
        calendar_ref=CalendarRef("fr-business-days"),
        revision=CalendarRevision(1),
        holidays=frozenset({date(2026, 1, 1)}),
    )


def test_scheduler_runs_first_business_day_at_schedule_local_time() -> None:
    calendar = _calendar()
    clock = MutableClock(_instant(2025, 12, 31))
    calls: list[str] = []
    scheduler = Scheduler(
        clock=clock,
        calendar_provider=InMemoryCalendarProvider([calendar]),
    )

    schedule_id = scheduler.add_schedule(
        id="month-open",
        target=lambda: calls.append("ran"),
        trigger=BusinessDayTrigger(
            ordinal=1,
            hour=8,
        ),
        timezone=Timezone("Europe/Paris"),
        calendar=calendar.snapshot_ref,
    )

    january = _instant(2026, 1, 2, 7)
    assert scheduler.inspect_schedule(schedule_id).next_run_time == january

    clock.set(january)
    result = scheduler.run_pending()

    assert len(result.executions) == 1
    assert calls == ["ran"]
    assert scheduler.inspect_schedule(schedule_id).next_run_time == _instant(
        2026,
        2,
        2,
        7,
    )


def test_public_scheduler_rejects_unbound_business_day_trigger() -> None:
    scheduler = Scheduler(clock=MutableClock(_instant(2025, 12, 31)))

    with pytest.raises(
        PyScheduleKitConfigurationError,
        match="requires a calendar binding",
    ):
        scheduler.add_schedule(
            id="invalid-business-trigger",
            target=lambda: None,
            trigger=BusinessDayTrigger(ordinal=1, hour=8),
            timezone=Timezone("Europe/Paris"),
        )
