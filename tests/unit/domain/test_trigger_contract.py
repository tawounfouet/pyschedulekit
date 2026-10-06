"""LOT-02 qualification tests for the common Trigger contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.time import Instant
from pyschedulekit.domain.trigger import Trigger
from pyschedulekit.testing import TriggerContractSuite, TriggerContractViolation


@dataclass(frozen=True, slots=True)
class SequenceTrigger:
    """Minimal deterministic Trigger used only to qualify the common contract."""

    instants: tuple[Instant, ...]

    def next_after(self, reference: Instant) -> Instant | None:
        return next((instant for instant in self.instants if instant > reference), None)


class NonProgressingTrigger:
    def next_after(self, reference: Instant) -> Instant | None:
        return reference


class NonDeterministicTrigger:
    def __init__(self, first: Instant, second: Instant) -> None:
        self._results = [first, second]

    def next_after(self, reference: Instant) -> Instant | None:
        del reference
        return self._results.pop(0)


def _instant(hour: int) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, 0, tzinfo=UTC))


def test_trigger_protocol_is_structural() -> None:
    trigger = SequenceTrigger((_instant(11),))

    assert isinstance(trigger, Trigger)


def test_next_after_returns_first_candidate_strictly_after_reference() -> None:
    trigger = SequenceTrigger((_instant(10), _instant(11), _instant(12)))

    assert trigger.next_after(_instant(10)) == _instant(11)


def test_none_represents_exhausted_trigger() -> None:
    trigger = SequenceTrigger((_instant(10),))

    assert trigger.next_after(_instant(10)) is None


def test_trigger_contract_suite_accepts_conforming_trigger() -> None:
    trigger = SequenceTrigger((_instant(10), _instant(11), _instant(12)))

    TriggerContractSuite.assert_conforms(
        trigger,
        (_instant(9), _instant(10), _instant(11), _instant(12)),
    )


def test_trigger_contract_suite_rejects_non_progressing_trigger() -> None:
    with pytest.raises(
        TriggerContractViolation,
        match="strictly after",
    ):
        TriggerContractSuite.assert_strict_progression(
            NonProgressingTrigger(),
            (_instant(10),),
        )


def test_trigger_contract_suite_rejects_non_deterministic_trigger() -> None:
    with pytest.raises(
        TriggerContractViolation,
        match="same result",
    ):
        TriggerContractSuite.assert_deterministic(
            NonDeterministicTrigger(_instant(11), _instant(12)),
            (_instant(10),),
        )


def test_trigger_contract_does_not_require_clock_or_runtime_context() -> None:
    trigger = SequenceTrigger((_instant(11),))

    assert trigger.next_after(_instant(10)) == _instant(11)
