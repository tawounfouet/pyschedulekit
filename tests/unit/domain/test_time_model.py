"""LOT-01 qualification tests for the temporal domain model."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from pyschedulekit.domain.time import (
    AmbiguousLocalTimeError,
    Duration,
    GracePeriod,
    Instant,
    InvalidDurationError,
    InvalidInstantError,
    InvalidTimeWindowError,
    NonexistentLocalTimeError,
    TimeWindow,
    Timezone,
)
from pyschedulekit.testing import FixedClock, MutableClock


def test_t_time_001_instant_requires_timezone_aware_datetime() -> None:
    instant = Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))

    assert instant.value == datetime(2026, 1, 1, 10, 0, tzinfo=UTC)


def test_t_time_002_naive_datetime_is_rejected() -> None:
    with pytest.raises(InvalidInstantError):
        Instant(datetime(2026, 1, 1, 10, 0))


def test_t_time_003_same_instant_with_different_offsets_is_equal() -> None:
    utc = Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    plus_one = Instant(
        datetime(2026, 1, 1, 11, 0, tzinfo=timezone(timedelta(hours=1)))
    )

    assert utc == plus_one


def test_t_time_004_timezone_is_not_a_fixed_offset() -> None:
    paris = Timezone("Europe/Paris")

    winter = paris.to_local(Instant(datetime(2026, 1, 15, 12, 0, tzinfo=UTC)))
    summer = paris.to_local(Instant(datetime(2026, 7, 15, 12, 0, tzinfo=UTC)))

    assert winter.utcoffset() == timedelta(hours=1)
    assert summer.utcoffset() == timedelta(hours=2)


def test_t_time_005_twenty_four_hours_is_not_always_same_local_clock_next_day() -> None:
    paris = Timezone("Europe/Paris")
    start = paris.resolve_local(datetime(2026, 3, 28, 12, 0))

    after_24h = start.add(Duration.hours(24))

    assert paris.to_local(after_24h).replace(tzinfo=None) == datetime(2026, 3, 29, 13, 0)


def test_t_time_006_fixed_clock_returns_same_now_until_explicit_change() -> None:
    initial = Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    clock = FixedClock(initial)

    assert clock.now() == clock.now() == initial


def test_t_time_007_mutable_clock_changes_only_when_explicitly_advanced() -> None:
    initial = Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    clock = MutableClock(initial)

    assert clock.now() == initial

    advanced = clock.advance(Duration.minutes(10))

    assert advanced == Instant(datetime(2026, 1, 1, 10, 10, tzinfo=UTC))
    assert clock.now() == advanced


def test_t_time_008_instant_normalizes_input_to_utc() -> None:
    instant = Instant(
        datetime(2026, 1, 1, 11, 0, tzinfo=timezone(timedelta(hours=1)))
    )

    assert instant.value.tzinfo is UTC
    assert instant.value == datetime(2026, 1, 1, 10, 0, tzinfo=UTC)


def test_t_time_009_time_window_is_half_open() -> None:
    start = Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    end = Instant(datetime(2026, 1, 1, 11, 0, tzinfo=UTC))
    window = TimeWindow(start=start, end=end)

    assert window.contains(start)
    assert window.contains(Instant(datetime(2026, 1, 1, 10, 59, 59, tzinfo=UTC)))
    assert not window.contains(end)


def test_t_time_010_nonexistent_dst_local_time_is_rejected() -> None:
    paris = Timezone("Europe/Paris")

    with pytest.raises(NonexistentLocalTimeError):
        paris.resolve_local(datetime(2026, 3, 29, 2, 30))


def test_t_time_011_ambiguous_dst_local_time_requires_explicit_fold() -> None:
    paris = Timezone("Europe/Paris")
    local = datetime(2026, 10, 25, 2, 30)

    with pytest.raises(AmbiguousLocalTimeError):
        paris.resolve_local(local)

    earlier = paris.resolve_local(local, fold=0)
    later = paris.resolve_local(local, fold=1)

    assert earlier < later
    assert later.value - earlier.value == timedelta(hours=1)


def test_t_time_012_leap_day_is_resolved() -> None:
    utc = Timezone("UTC")

    leap_day = utc.resolve_local(datetime(2028, 2, 29, 12, 0))

    assert leap_day == Instant(datetime(2028, 2, 29, 12, 0, tzinfo=UTC))


def test_duration_rejects_negative_values() -> None:
    with pytest.raises(InvalidDurationError):
        Duration.seconds(-1)


def test_time_window_requires_strictly_positive_width() -> None:
    instant = Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))

    with pytest.raises(InvalidTimeWindowError):
        TimeWindow(start=instant, end=instant)


def test_grace_period_builds_deadline_from_scheduled_instant() -> None:
    scheduled_at = Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    grace = GracePeriod.seconds(30)

    assert grace.deadline_for(scheduled_at) == Instant(
        datetime(2026, 1, 1, 10, 0, 30, tzinfo=UTC)
    )
