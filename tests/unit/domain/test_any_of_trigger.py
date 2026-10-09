"""CMP-00 qualification for the pure temporal composite-trigger contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass
from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.time import Instant
from pyschedulekit.domain.trigger import Trigger
from pyschedulekit.domain.triggers import (
    AnyOfTrigger,
    CompositeTriggerContractError,
    DateTrigger,
    InvalidCompositeTriggerError,
)
from pyschedulekit.testing import TriggerContractSuite


def _instant(hour: int, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


@dataclass(frozen=True, slots=True)
class SequenceTrigger:
    instants: tuple[Instant, ...]

    def next_after(self, reference: Instant) -> Instant | None:
        return next((instant for instant in self.instants if instant > reference), None)


class NonProgressingTrigger:
    def next_after(self, reference: Instant) -> Instant:
        return reference


class WrongTypeTrigger:
    def next_after(self, reference: Instant) -> Instant:
        del reference
        return "2026-01-01T10:00:00Z"  # type: ignore[return-value]


class TemporalAndCalendarAwareTrigger:
    def next_after(self, reference: Instant) -> Instant:
        return _instant(reference.value.hour + 1)

    def next_after_with_calendar(self, reference: Instant, **kwargs: object) -> Instant:
        del kwargs
        return self.next_after(reference)


def test_any_of_requires_at_least_two_children() -> None:
    with pytest.raises(InvalidCompositeTriggerError, match="at least two"):
        AnyOfTrigger()

    with pytest.raises(InvalidCompositeTriggerError, match="at least two"):
        AnyOfTrigger(DateTrigger(at=_instant(10)))


def test_any_of_rejects_non_trigger_children() -> None:
    with pytest.raises(InvalidCompositeTriggerError, match="index 1"):
        AnyOfTrigger(DateTrigger(at=_instant(10)), object())  # type: ignore[arg-type]


def test_any_of_rejects_children_that_hide_calendar_aware_semantics() -> None:
    with pytest.raises(InvalidCompositeTriggerError, match="purely temporal"):
        AnyOfTrigger(
            DateTrigger(at=_instant(10)),
            TemporalAndCalendarAwareTrigger(),
        )


def test_any_of_selects_earliest_candidate_independent_of_child_order() -> None:
    early = DateTrigger(at=_instant(10))
    late = DateTrigger(at=_instant(11))

    assert AnyOfTrigger(late, early).next_after(_instant(9)) == _instant(10)
    assert AnyOfTrigger(early, late).next_after(_instant(9)) == _instant(10)


def test_any_of_ignores_exhausted_children_until_all_are_exhausted() -> None:
    trigger = AnyOfTrigger(
        DateTrigger(at=_instant(10)),
        DateTrigger(at=_instant(12)),
    )

    assert trigger.next_after(_instant(10)) == _instant(12)
    assert trigger.next_after(_instant(12)) is None


def test_any_of_emits_shared_instant_once_then_advances_all_children() -> None:
    trigger = AnyOfTrigger(
        SequenceTrigger((_instant(10), _instant(11))),
        SequenceTrigger((_instant(10), _instant(12))),
    )

    first = trigger.next_after(_instant(9))
    assert first == _instant(10)

    second = trigger.next_after(first)
    assert second == _instant(11)
    assert trigger.next_after(second) == _instant(12)


@pytest.mark.parametrize("child", [NonProgressingTrigger(), WrongTypeTrigger()])
def test_any_of_fails_closed_when_child_breaks_trigger_contract(child: Trigger) -> None:
    trigger = AnyOfTrigger(child, DateTrigger(at=_instant(11)))

    with pytest.raises(CompositeTriggerContractError, match="index 0"):
        trigger.next_after(_instant(10))


def test_any_of_propagates_child_failures() -> None:
    class FailingTrigger:
        def next_after(self, reference: Instant) -> Instant | None:
            del reference
            raise LookupError("child failure")

    trigger = AnyOfTrigger(FailingTrigger(), DateTrigger(at=_instant(11)))

    with pytest.raises(LookupError, match="child failure"):
        trigger.next_after(_instant(10))


def test_any_of_is_immutable_and_conforms_to_trigger_protocol() -> None:
    trigger = AnyOfTrigger(
        SequenceTrigger((_instant(10), _instant(12))),
        SequenceTrigger((_instant(11), _instant(13))),
    )

    assert isinstance(trigger, Trigger)
    TriggerContractSuite.assert_conforms(
        trigger,
        (_instant(9), _instant(10), _instant(11), _instant(12), _instant(13)),
    )

    with pytest.raises(FrozenInstanceError):
        trigger.triggers = ()  # type: ignore[misc]
