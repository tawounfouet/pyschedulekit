"""Built-in temporal Trigger implementations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from pyschedulekit.domain.time import Duration, Instant


class InvalidIntervalTriggerError(ValueError):
    """Raised when an IntervalTrigger has no strictly positive interval."""


@dataclass(frozen=True, slots=True)
class DateTrigger:
    """Finite Trigger that emits one absolute Instant."""

    at: Instant

    def next_after(self, reference: Instant) -> Instant | None:
        """Return the one occurrence when it is still strictly in the future."""

        return self.at if reference < self.at else None


@dataclass(frozen=True, slots=True)
class IntervalTrigger:
    """Fixed-rate Trigger anchored to one absolute Instant.

    Occurrences are always calculated from the anchor:

        anchor + n * every

    Actual execution time never shifts the recurrence.
    """

    every: Duration
    anchor: Instant

    def __post_init__(self) -> None:
        if self.every.value <= timedelta(0):
            raise InvalidIntervalTriggerError(
                "IntervalTrigger requires a strictly positive interval."
            )

    def next_after(self, reference: Instant) -> Instant:
        """Return the first anchored occurrence strictly after reference.

        Calculation is direct. It does not iterate through historical
        occurrences, even when the reference is far from the anchor.
        """

        if reference < self.anchor:
            return self.anchor

        elapsed = reference.value - self.anchor.value
        completed_intervals = elapsed // self.every.value
        return self.anchor.add(Duration(self.every.value * (completed_intervals + 1)))
