"""CAL-00 qualification for business-calendar value objects."""

from datetime import date

import pytest

from pyschedulekit.domain.calendar import (
    BusinessCalendar,
    CalendarRef,
    CalendarRevision,
    CalendarSnapshotRef,
)


def test_calendar_ref_requires_non_empty_identity() -> None:
    assert CalendarRef("fr-business-days").value == "fr-business-days"

    with pytest.raises(ValueError, match="must not be empty"):
        CalendarRef("   ")


def test_calendar_revision_is_positive_and_monotonic() -> None:
    revision = CalendarRevision()

    assert revision.value == 1
    assert revision.next() == CalendarRevision(2)

    with pytest.raises(ValueError, match="greater than or equal to 1"):
        CalendarRevision(0)


def test_snapshot_ref_identifies_one_exact_calendar_revision() -> None:
    snapshot = CalendarSnapshotRef(
        calendar_ref=CalendarRef("finance-days"),
        revision=CalendarRevision(7),
    )

    assert snapshot == CalendarSnapshotRef(
        calendar_ref=CalendarRef("finance-days"),
        revision=CalendarRevision(7),
    )
    assert hash(snapshot) == hash(
        CalendarSnapshotRef(
            calendar_ref=CalendarRef("finance-days"),
            revision=CalendarRevision(7),
        )
    )


def test_default_business_calendar_uses_monday_to_friday() -> None:
    calendar = BusinessCalendar(calendar_ref=CalendarRef("default"))

    assert calendar.is_working_day(date(2026, 1, 5))  # Monday
    assert calendar.is_working_day(date(2026, 1, 9))  # Friday
    assert not calendar.is_working_day(date(2026, 1, 10))  # Saturday
    assert not calendar.is_working_day(date(2026, 1, 11))  # Sunday


def test_holiday_blocks_normally_working_weekday() -> None:
    holiday = date(2026, 7, 14)
    calendar = BusinessCalendar(
        calendar_ref=CalendarRef("fr-business-days"),
        holidays=frozenset({holiday}),
    )

    assert holiday.weekday() == 1
    assert not calendar.is_working_day(holiday)


def test_extra_working_day_allows_normally_closed_weekend() -> None:
    saturday = date(2026, 1, 10)
    calendar = BusinessCalendar(
        calendar_ref=CalendarRef("exception-calendar"),
        extra_working_days=frozenset({saturday}),
    )

    assert saturday.weekday() == 5
    assert calendar.is_working_day(saturday)


def test_calendar_rejects_invalid_weekday_number() -> None:
    with pytest.raises(ValueError, match="0 \(Monday\) to 6 \(Sunday\)"):
        BusinessCalendar(
            calendar_ref=CalendarRef("invalid"),
            working_weekdays=frozenset({0, 7}),
        )


def test_holidays_and_extra_working_days_must_be_disjoint() -> None:
    ambiguous = date(2026, 5, 1)

    with pytest.raises(ValueError, match="must be disjoint"):
        BusinessCalendar(
            calendar_ref=CalendarRef("ambiguous"),
            holidays=frozenset({ambiguous}),
            extra_working_days=frozenset({ambiguous}),
        )


def test_custom_working_week_is_supported_without_global_assumptions() -> None:
    calendar = BusinessCalendar(
        calendar_ref=CalendarRef("regional-week"),
        working_weekdays=frozenset({6, 0, 1, 2, 3}),
    )

    assert calendar.is_working_day(date(2026, 1, 4))  # Sunday
    assert not calendar.is_working_day(date(2026, 1, 9))  # Friday


def test_business_calendar_exposes_deterministic_snapshot_reference() -> None:
    calendar = BusinessCalendar(
        calendar_ref=CalendarRef("market"),
        revision=CalendarRevision(4),
    )

    assert calendar.snapshot_ref == CalendarSnapshotRef(
        calendar_ref=CalendarRef("market"),
        revision=CalendarRevision(4),
    )
