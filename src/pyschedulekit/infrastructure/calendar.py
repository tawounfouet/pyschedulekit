"""In-memory BusinessCalendar provider."""

from __future__ import annotations

from collections.abc import Iterable
from threading import RLock

from pyschedulekit.domain.calendar import (
    BusinessCalendar,
    CalendarRef,
    CalendarRevision,
    CalendarSnapshotRef,
)
from pyschedulekit.errors import PyScheduleKitConfigurationError


class InMemoryCalendarProvider:
    """Thread-safe process-local provider with explicit versioned registrations."""

    def __init__(self, calendars: Iterable[BusinessCalendar] = ()) -> None:
        self._lock = RLock()
        self._calendars: dict[tuple[CalendarRef, CalendarRevision], BusinessCalendar] = {}

        for calendar in calendars:
            self.register(calendar)

    def register(
        self,
        calendar: BusinessCalendar,
        *,
        replace: bool = False,
    ) -> None:
        """Register one exact calendar revision."""

        key = (calendar.calendar_ref, calendar.revision)
        with self._lock:
            if key in self._calendars and not replace:
                raise PyScheduleKitConfigurationError(
                    "BusinessCalendar revision is already registered: "
                    f"{calendar.calendar_ref.value!r} revision {calendar.revision.value}."
                )
            self._calendars[key] = calendar

    def resolve(
        self,
        reference: CalendarRef,
        *,
        revision: CalendarRevision | None = None,
    ) -> BusinessCalendar:
        """Resolve the latest or requested exact revision."""

        with self._lock:
            if revision is not None:
                calendar = self._calendars.get((reference, revision))
                if calendar is None:
                    raise PyScheduleKitConfigurationError(
                        "BusinessCalendar revision is not registered: "
                        f"{reference.value!r} revision {revision.value}."
                    )
                return calendar

            candidates = [
                calendar
                for (calendar_ref, _), calendar in self._calendars.items()
                if calendar_ref == reference
            ]

        if not candidates:
            raise PyScheduleKitConfigurationError(
                f"BusinessCalendar {reference.value!r} is not registered."
            )

        return max(candidates, key=lambda calendar: calendar.revision)

    @property
    def references(self) -> tuple[CalendarSnapshotRef, ...]:
        """Return a deterministic snapshot of every registered revision."""

        with self._lock:
            return tuple(sorted(calendar.snapshot_ref for calendar in self._calendars.values()))
