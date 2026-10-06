"""LOT-03 qualification tests for DateTrigger and IntervalTrigger."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.trigger import Trigger
from pyschedulekit.domain.triggers import (
    DateTrigger,
    IntervalTrigger,
    InvalidIntervalTriggerError,
)
from pyschedulekit.testing import TriggerContractSuite


def _instant(
    year: int = 2026,
    month: int = 1,
    day: int = 1,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
) -> Instant:
    return Instant(datetime(year, month, day, hour, minute, second, tzinfo=UTC))


def test_t_trg_001_date_trigger_emits_one_occurrence() -> None:
    at = _instant(hour=10)
    trigger = DateTrigger(at=at)

    assert trigger.next_after(_instant(hour=9)) == at


def test_t_trg_002_date_trigger_is_exhausted_at_or_after_occurrence() -> None:
    at = _instant(hour=10)
    trigger = DateTrigger(at=at)

    assert trigger.next_after(at) is None
    assert trigger.next_after(_instant(hour=11)) is None


def test_t_trg_003_date_trigger_is_immutable_and_conforms() -> None:
    trigger = DateTrigger(at=_instant(hour=10))

    assert isinstance(trigger, Trigger)
    TriggerContractSuite.assert_conforms(
        trigger,
        (_instant(hour=9), _instant(hour=10), _instant(hour=11)),
    )

    with pytest.raises(FrozenInstanceError):
        trigger.at = _instant(hour=12)  # type: ignore[misc]


def test_t_trg_010_interval_requires_strictly_positive_duration() -> None:
    with pytest.raises(InvalidIntervalTriggerError):
        IntervalTrigger(
            every=Duration.seconds(0),
            anchor=_instant(hour=10),
        )


def test_t_trg_011_interval_progresses_from_anchor() -> None:
    trigger = IntervalTrigger(
        every=Duration.minutes(10),
        anchor=_instant(hour=10),
    )

    assert trigger.next_after(_instant(hour=9)) == _instant(hour=10)
    assert trigger.next_after(_instant(hour=10)) == _instant(hour=10, minute=10)
    assert trigger.next_after(_instant(hour=10, minute=10)) == _instant(hour=10, minute=20)
    assert trigger.next_after(_instant(hour=10, minute=20)) == _instant(hour=10, minute=30)


def test_t_trg_012_interval_result_is_always_strictly_after_reference() -> None:
    trigger = IntervalTrigger(
        every=Duration.minutes(10),
        anchor=_instant(hour=10),
    )
    references = (
        _instant(hour=9),
        _instant(hour=10),
        _instant(hour=10, minute=1),
        _instant(hour=10, minute=10),
        _instant(hour=12),
    )

    TriggerContractSuite.assert_strict_progression(trigger, references)


def test_t_trg_013_interval_has_no_cumulative_drift() -> None:
    anchor = _instant(hour=10)
    interval = Duration.seconds(7)
    trigger = IntervalTrigger(every=interval, anchor=anchor)
    exact_occurrence = anchor.add(Duration.seconds(7 * 10_000))

    assert trigger.next_after(
        exact_occurrence.add(Duration.seconds(-0))  # preserve exact Instant explicitly
    ) == anchor.add(Duration.seconds(7 * 10_001))


def test_t_trg_013_interval_far_sequence_remains_anchor_based() -> None:
    anchor = _instant(hour=10)
    trigger = IntervalTrigger(
        every=Duration.minutes(10),
        anchor=anchor,
    )
    reference = anchor.add(Duration.minutes(100_000)).add(Duration.seconds(1))

    expected = anchor.add(Duration.minutes(100_010))

    assert trigger.next_after(reference) == expected


def test_t_trg_014_late_execution_time_does_not_shift_fixed_rate_schedule() -> None:
    anchor = _instant(hour=10)
    trigger = IntervalTrigger(
        every=Duration.minutes(10),
        anchor=anchor,
    )

    actual_execution_time = _instant(hour=10, minute=12)

    assert trigger.next_after(actual_execution_time) == _instant(hour=10, minute=20)


def test_t_trg_015_interval_computes_far_future_occurrence_directly() -> None:
    anchor = _instant(2026, 1, 1)
    trigger = IntervalTrigger(
        every=Duration.seconds(7),
        anchor=anchor,
    )
    reference = _instant(2126, 1, 1)

    candidate = trigger.next_after(reference)

    assert candidate > reference
    elapsed = candidate.value - anchor.value
    assert elapsed % timedelta(seconds=7) == timedelta(0)


def test_interval_trigger_is_immutable_and_conforms_to_trigger_protocol() -> None:
    trigger = IntervalTrigger(
        every=Duration.minutes(10),
        anchor=_instant(hour=10),
    )

    assert isinstance(trigger, Trigger)
    TriggerContractSuite.assert_conforms(
        trigger,
        (
            _instant(hour=9),
            _instant(hour=10),
            _instant(hour=10, minute=1),
            _instant(hour=11),
        ),
    )

    with pytest.raises(FrozenInstanceError):
        trigger.anchor = _instant(hour=11)  # type: ignore[misc]
