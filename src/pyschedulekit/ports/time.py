"""Time-related ports used by application services and runtimes."""

from __future__ import annotations

from typing import Protocol

from pyschedulekit.domain.time import Instant


class Clock(Protocol):
    """Source of absolute wall-clock time."""

    def now(self) -> Instant:
        """Return the current absolute Instant."""
        ...
