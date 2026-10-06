"""Reusable conformance assertions for Trigger implementations."""

from __future__ import annotations

from collections.abc import Iterable

from pyschedulekit.domain.time import Instant
from pyschedulekit.domain.trigger import Trigger


class TriggerContractViolation(AssertionError):
    """Raised when a Trigger breaks the common temporal contract."""


class TriggerContractSuite:
    """Reusable semantic checks for concrete Trigger implementations."""

    @staticmethod
    def assert_deterministic(trigger: Trigger, references: Iterable[Instant]) -> None:
        for reference in references:
            first = trigger.next_after(reference)
            second = trigger.next_after(reference)
            if first != second:
                raise TriggerContractViolation(
                    "Trigger must return the same result for the same reference."
                )

    @staticmethod
    def assert_strict_progression(trigger: Trigger, references: Iterable[Instant]) -> None:
        for reference in references:
            candidate = trigger.next_after(reference)
            if candidate is not None and candidate <= reference:
                raise TriggerContractViolation(
                    "Trigger.next_after() must return an Instant strictly after the reference."
                )

    @classmethod
    def assert_conforms(cls, trigger: Trigger, references: Iterable[Instant]) -> None:
        """Run all common semantic checks against a Trigger."""

        refs = tuple(references)
        cls.assert_deterministic(trigger, refs)
        cls.assert_strict_progression(trigger, refs)
