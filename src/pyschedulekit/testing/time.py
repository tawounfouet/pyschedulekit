"""Deterministic clocks for tests, simulations, and examples."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.domain.time import Duration, Instant


@dataclass(frozen=True, slots=True)
class FixedClock:
    """Clock that always returns the same Instant."""

    current: Instant

    def now(self) -> Instant:
        return self.current


class MutableClock:
    """Clock whose current Instant changes only when explicitly instructed."""

    def __init__(self, current: Instant) -> None:
        self._current = current

    def now(self) -> Instant:
        return self._current

    def set(self, instant: Instant) -> None:
        self._current = instant

    def advance(self, duration: Duration) -> Instant:
        self._current = self._current.add(duration)
        return self._current
