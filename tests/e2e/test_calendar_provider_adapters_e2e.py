"""CAL-05 end-to-end qualification for external CalendarProvider adapters."""

import json
from datetime import UTC, date, datetime

from pyschedulekit import (
    BusinessCalendar,
    BusinessDayTrigger,
    CalendarRef,
    CalendarRevision,
    FileCalendarProvider,
    Instant,
    Scheduler,
    SqliteCalendarProvider,
    SqliteUnitOfWorkFactory,
)
from pyschedulekit.testing import MutableClock


def _instant(year: int, month: int, day: int, hour: int = 0) -> Instant:
    return Instant(datetime(year, month, day, hour, tzinfo=UTC))


def _calendar() -> BusinessCalendar:
    return BusinessCalendar(
        calendar_ref=CalendarRef("finance-days"),
        revision=CalendarRevision(1),
        holidays=frozenset({date(2026, 1, 1)}),
    )


def test_file_provider_drives_public_business_day_schedule(tmp_path) -> None:
    calendar_file = tmp_path / "calendars.json"
    calendar_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "calendars": [
                    {
                        "schema_version": 1,
                        "reference": "finance-days",
                        "revision": 1,
                        "working_weekdays": [0, 1, 2, 3, 4],
                        "holidays": ["2026-01-01"],
                        "extra_working_days": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    clock = MutableClock(_instant(2025, 12, 31, 12))
    executions: list[str] = []
    scheduler = Scheduler(
        clock=clock,
        calendar_provider=FileCalendarProvider(calendar_file),
    )

    schedule_id = scheduler.add_schedule(
        id="file-calendar",
        target=lambda: executions.append("ran"),
        trigger=BusinessDayTrigger(ordinal=1, hour=8),
        calendar=_calendar().snapshot_ref,
    )

    assert scheduler.inspect_schedule(schedule_id).next_run_time == _instant(
        2026,
        1,
        2,
        8,
    )

    clock.set(_instant(2026, 1, 2, 8))
    result = scheduler.run_pending()

    assert len(result.executions) == 1
    assert executions == ["ran"]


def test_sqlite_calendar_provider_coexists_with_scheduler_database(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    calendar = _calendar()
    calendar_provider = SqliteCalendarProvider(database)
    calendar_provider.register(calendar)
    clock = MutableClock(_instant(2025, 12, 31, 12))
    executions: list[str] = []
    scheduler = Scheduler(
        clock=clock,
        uow_factory=SqliteUnitOfWorkFactory(database),
        calendar_provider=calendar_provider,
    )

    schedule_id = scheduler.add_schedule(
        id="sqlite-calendar",
        target=lambda: executions.append("ran"),
        trigger=BusinessDayTrigger(ordinal=1, hour=8),
        calendar=calendar.snapshot_ref,
    )

    assert scheduler.inspect_schedule(schedule_id).next_run_time == _instant(
        2026,
        1,
        2,
        8,
    )

    clock.set(_instant(2026, 1, 2, 8))
    result = scheduler.run_pending()

    assert len(result.executions) == 1
    assert executions == ["ran"]
    assert (
        SqliteCalendarProvider(database).resolve(
            CalendarRef("finance-days"),
            revision=CalendarRevision(1),
        )
        == calendar
    )
