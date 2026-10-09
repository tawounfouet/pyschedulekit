"""Business-calendar resolution port."""

from __future__ import annotations

from typing import Protocol

from pyschedulekit.domain.calendar import (
    BusinessCalendar,
    CalendarRef,
    CalendarRevision,
)


class CalendarProvider(Protocol):
    """Resolve a logical calendar to its latest or one exact historical revision."""

    def resolve(
        self,
        reference: CalendarRef,
        *,
        revision: CalendarRevision | None = None,
    ) -> BusinessCalendar:
        """Resolve a BusinessCalendar without exposing storage/integration details."""
        ...
