"""CAL-02 qualification for calendar-aware occurrence planning."""

from datetime import UTC, date, datetime

import pytest

from pyschedulekit.domain.calendar import BusinessCalendar, CalendarRef, CalendarRevision
from pyschedulekit.domain.calendar_planning import (
    CalendarBindingError,
    CalendarOccurrencePlanner,
    CalendarPlanningLimitExceededError,
)
from pyschedulekit.domain.occurrence import OccurrencePlanner
from pyschedulekit.domain.schedule import Schedule, ScheduleDefinition, ScheduleId, TargetRef
from pyschedulekit.domain.time import Duration, Instant, Timezone
from pyschedulekit.domain.triggers import DateTrigger, IntervalTrigger


def _instant(day: int, hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, day, hour, minute, tzinfo=UTC))


def _calendar(
    *,
    revision: int = 1,
    working_weekdays: frozenset[int] = frozenset({0, 1, 2, 3, 4}),
    holidays: frozenset[date] = frozenset(),
    extra_working_days: frozenset[date] = frozenset(),
) -> BusinessCalendar:
    return BusinessCalendar(
        calendar_ref=CalendarRef("business-days"),
        revision=CalendarRevision(revision),
        working_weekdays=working_weekdays,
        holidays=holidays,
        extra_working_days=extra_working_days,
    )


def _daily_trigger() -> IntervalTrigger:
    return IntervalTrigger(
        every=Duration.days(1),
        anchor=_instant(2),
    )


def test_planner_skips_weekend_to_next_working_day() -> None:
    calendar = _calendar()
    planner = CalendarOccurrencePlanner()

    next_run = planner.next_after(
        trigger=_daily_trigger(),
        reference=_instant(2),
        timezone=Timezone("UTC"),
        binding=calendar.snapshot_ref,
        calendar=calendar,
    )

    assert next_run == _instant(5)


def test_planner_skips_explicit_holiday_after_weekend() -> None:
    calendar = _calendar(holidays=frozenset({date(2026, 1, 5)}))

    next_run = CalendarOccurrencePlanner().next_after(
        trigger=_daily_trigger(),
        reference=_instant(2),
        timezone=Timezone("UTC"),
        binding=calendar.snapshot_ref,
        calendar=calendar,
    )

    assert next_run == _instant(6)


def test_extra_working_day_allows_exceptional_saturday() -> None:
    calendar = _calendar(extra_working_days=frozenset({date(2026, 1, 3)}))

    next_run = CalendarOccurrencePlanner().next_after(
        trigger=_daily_trigger(),
        reference=_instant(2),
        timezone=Timezone("UTC"),
        binding=calendar.snapshot_ref,
        calendar=calendar,
    )

    assert next_run == _instant(3)


def test_calendar_uses_schedule_local_date_not_utc_date() -> None:
    calendar = _calendar(working_weekdays=frozenset({0}))
    candidate = Instant(datetime(2026, 1, 4, 23, 30, tzinfo=UTC))

    next_run = CalendarOccurrencePlanner().next_after(
        trigger=DateTrigger(at=candidate),
        reference=Instant(datetime(2026, 1, 4, 23, 0, tzinfo=UTC)),
        timezone=Timezone("Europe/Paris"),
        binding=calendar.snapshot_ref,
        calendar=calendar,
    )

    assert next_run == candidate


def test_calendar_binding_must_match_exact_resolved_revision() -> None:
    calendar = _calendar(revision=2)

    with pytest.raises(CalendarBindingError, match="does not match"):
        CalendarOccurrencePlanner().next_after(
            trigger=_daily_trigger(),
            reference=_instant(2),
            timezone=Timezone("UTC"),
            binding=_calendar(revision=1).snapshot_ref,
            calendar=calendar,
        )


def test_bound_schedule_fails_closed_without_resolved_calendar() -> None:
    calendar = _calendar()

    with pytest.raises(CalendarBindingError, match="requires its exact BusinessCalendar"):
        Schedule.create(
            schedule_id=ScheduleId("missing-calendar"),
            definition=ScheduleDefinition(
                target=TargetRef.python("jobs:calendar"),
                trigger=_daily_trigger(),
                calendar=calendar.snapshot_ref,
            ),
            reference=_instant(2),
        )


def test_calendar_candidate_scan_is_bounded() -> None:
    calendar = _calendar(working_weekdays=frozenset())
    planner = CalendarOccurrencePlanner(max_candidates=3)

    with pytest.raises(CalendarPlanningLimitExceededError, match="candidate limit"):
        planner.next_after(
            trigger=_daily_trigger(),
            reference=_instant(2),
            timezone=Timezone("UTC"),
            binding=calendar.snapshot_ref,
            calendar=calendar,
        )


def test_schedule_checkpoint_jumps_directly_to_next_valid_occurrence() -> None:
    calendar = _calendar()

    schedule = Schedule.create(
        schedule_id=ScheduleId("calendar-aware"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:calendar"),
            trigger=_daily_trigger(),
            calendar=calendar.snapshot_ref,
        ),
        reference=_instant(2),
        calendar=calendar,
    )

    assert schedule.next_run_time == _instant(5)


def test_backlog_contains_only_calendar_valid_occurrences() -> None:
    calendar = _calendar()
    schedule = Schedule.create(
        schedule_id=ScheduleId("calendar-backlog"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:calendar"),
            trigger=_daily_trigger(),
            calendar=calendar.snapshot_ref,
        ),
        reference=_instant(1),
        calendar=calendar,
    )

    backlog = OccurrencePlanner().due_backlog(
        schedule,
        until=_instant(6),
        limit=10,
        calendar=calendar,
    )

    assert [occurrence.scheduled_at for occurrence in backlog.occurrences] == [
        _instant(2),
        _instant(5),
        _instant(6),
    ]
    assert backlog.has_more is False
