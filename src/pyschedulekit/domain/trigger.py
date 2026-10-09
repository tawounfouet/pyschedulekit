"""Core trigger contract for temporal occurrence calculation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pyschedulekit.domain.calendar import BusinessCalendar
from pyschedulekit.domain.time import Instant, Timezone


@runtime_checkable
class Trigger(Protocol):
    """Pure strategy that calculates the next candidate occurrence.

    A Trigger answers only a temporal question: given an absolute reference
    Instant, what is the next candidate Instant strictly after it?

    Implementations must be deterministic for the same inputs, perform no I/O,
    read no ambient clock, and return either an Instant strictly greater than
    the reference or None when the trigger is exhausted.
    """

    def next_after(self, reference: Instant) -> Instant | None:
        """Return the first candidate Instant strictly after the reference."""
        ...


@runtime_checkable
class CalendarAwareTrigger(Protocol):
    """Trigger whose occurrence semantics require one resolved BusinessCalendar."""

    def next_after_with_calendar(
        self,
        reference: Instant,
        *,
        timezone: Timezone,
        calendar: BusinessCalendar,
    ) -> Instant | None:
        """Return the first occurrence strictly after reference using calendar context."""
        ...
