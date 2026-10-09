"""CAL-03 qualification for BusinessDayTrigger semantics."""

from datetime import UTC, date, datetime

import pytest

from pyschedulekit.domain.calendar import BusinessCalendar, CalendarRef, CalendarRevision
from pyschedulekit.domain.calendar_planning import CalendarBindingError, CalendarOccurrencePlanner
from pyschedulekit.domain.time import Instant, NonexistentLocalTimeError, Timezone
from pyschedulekit.domain.triggers import (
    BusinessDaySearchLimitError,
    BusinessDayTrigger,
    CronNonexistentTimePolicy,
    InvalidBusinessDayTriggerError,
)


def _instant(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> Instant:
    return Instant(datetime(year, month, day, hour, minute, tzinfo=UTC))


def _calendar(
    *,
    holidays: frozenset[date] = frozenset(),
    extra_working_days: frozenset[date] = frozenset(),
    working_weekdays: frozenset[int] = frozenset({0, 1, 2, 3, 4}),
) -> BusinessCalendar:
    return BusinessCalendar(
        calendar_ref=CalendarRef("business-days"),
        revision=CalendarRevision(1),
        working_weekdays=working_weekdays,
        holidays=holidays,
        extra_working_days=extra_working_days,
    )


def _next(
    trigger: BusinessDayTrigger,
    *,
    reference: Instant,
    calendar: BusinessCalendar,
    timezone: str = "UTC",
) -> Instant:
    result = CalendarOccurrencePlanner().next_after(
        trigger=trigger,
        reference=reference,
        timezone=Timezone(timezone),
        binding=calendar.snapshot_ref,
        calendar=calendar,
    )
    assert result is not None
    return result


def test_first_working_day_skips_holiday() -> None:
    calendar = _calendar(holidays=frozenset({date(2026, 1, 1)}))

    result = _next(
        BusinessDayTrigger(ordinal=1, hour=8),
        reference=_instant(2025, 12, 31),
        calendar=calendar,
    )

    assert result == _instant(2026, 1, 2, 8)


def test_last_working_day_skips_weekend_month_end() -> None:
    result = _next(
        BusinessDayTrigger(ordinal=-1, hour=18),
        reference=_instant(2026, 1, 1),
        calendar=_calendar(),
    )

    assert result == _instant(2026, 1, 30, 18)


def test_second_working_day_counts_only_allowed_dates() -> None:
    calendar = _calendar(holidays=frozenset({date(2026, 1, 1)}))

    result = _next(
        BusinessDayTrigger(ordinal=2, hour=9),
        reference=_instant(2025, 12, 31),
        calendar=calendar,
    )

    assert result == _instant(2026, 1, 5, 9)


def test_extra_working_saturday_can_be_selected() -> None:
    calendar = _calendar(
        holidays=frozenset({date(2026, 1, 1), date(2026, 1, 2)}),
        extra_working_days=frozenset({date(2026, 1, 3)}),
    )

    result = _next(
        BusinessDayTrigger(ordinal=1, hour=10),
        reference=_instant(2025, 12, 31),
        calendar=calendar,
    )

    assert result == _instant(2026, 1, 3, 10)


def test_trigger_uses_schedule_timezone_for_local_civil_time() -> None:
    result = _next(
        BusinessDayTrigger(ordinal=1, hour=8),
        reference=_instant(2025, 12, 31),
        calendar=_calendar(),
        timezone="Europe/Paris",
    )

    assert result == _instant(2026, 1, 1, 7)


def test_reference_at_current_occurrence_advances_to_next_month() -> None:
    trigger = BusinessDayTrigger(ordinal=1, hour=8)
    calendar = _calendar()

    result = _next(
        trigger,
        reference=_instant(2026, 1, 1, 8),
        calendar=calendar,
    )

    assert result == _instant(2026, 2, 2, 8)


@pytest.mark.parametrize(
    "kwargs",
    (
        {"ordinal": 0},
        {"ordinal": 32},
        {"ordinal": -32},
        {"hour": -1},
        {"hour": 24},
        {"minute": -1},
        {"minute": 60},
    ),
)
def test_invalid_business_day_configuration_is_rejected(kwargs: dict[str, int]) -> None:
    with pytest.raises(InvalidBusinessDayTriggerError):
        BusinessDayTrigger(**kwargs)


def test_calendar_aware_trigger_requires_schedule_binding() -> None:
    with pytest.raises(CalendarBindingError, match="requires a Schedule calendar binding"):
        CalendarOccurrencePlanner().next_after(
            trigger=BusinessDayTrigger(),
            reference=_instant(2025, 12, 31),
            timezone=Timezone("UTC"),
            binding=None,
            calendar=None,
        )


def test_impossible_calendar_search_is_bounded() -> None:
    calendar = _calendar(working_weekdays=frozenset())

    with pytest.raises(BusinessDaySearchLimitError, match="bounded search horizon"):
        _next(
            BusinessDayTrigger(),
            reference=_instant(2025, 12, 31),
            calendar=calendar,
        )


def test_nonexistent_business_time_can_fail_explicitly() -> None:
    calendar = _calendar(
        working_weekdays=frozenset(),
        extra_working_days=frozenset({date(2026, 3, 29)}),
    )

    with pytest.raises(NonexistentLocalTimeError):
        _next(
            BusinessDayTrigger(
                ordinal=1,
                hour=2,
                minute=30,
                nonexistent_time=CronNonexistentTimePolicy.RAISE,
            ),
            reference=_instant(2026, 3, 1),
            calendar=calendar,
            timezone="Europe/Paris",
        )
