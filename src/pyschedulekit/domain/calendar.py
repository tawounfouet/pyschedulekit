"""Business-calendar value objects for deterministic scheduling decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True, order=True)
class CalendarRef:
    """Stable logical identity of one shared business calendar."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("CalendarRef must not be empty.")


@dataclass(frozen=True, slots=True, order=True)
class CalendarRevision:
    """Immutable revision number of a BusinessCalendar definition."""

    value: int = 1

    def __post_init__(self) -> None:
        if self.value < 1:
            raise ValueError("CalendarRevision must be greater than or equal to 1.")

    def next(self) -> CalendarRevision:
        return CalendarRevision(self.value + 1)


@dataclass(frozen=True, slots=True, order=True)
class CalendarSnapshotRef:
    """Deterministic reference to one exact calendar revision."""

    calendar_ref: CalendarRef
    revision: CalendarRevision


@dataclass(frozen=True, slots=True)
class BusinessCalendar:
    """Immutable working-day rules for one exact calendar revision.

    Weekdays use Python's date.weekday() convention: Monday=0 through Sunday=6.
    Explicit holidays and extra working days must be disjoint so no hidden precedence rule
    is required.
    """

    calendar_ref: CalendarRef
    revision: CalendarRevision = field(default_factory=CalendarRevision)
    working_weekdays: frozenset[int] = field(
        default_factory=lambda: frozenset({0, 1, 2, 3, 4})
    )
    holidays: frozenset[date] = field(default_factory=frozenset)
    extra_working_days: frozenset[date] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        invalid_weekdays = self.working_weekdays - frozenset(range(7))
        if invalid_weekdays:
            raise ValueError(
                "BusinessCalendar weekdays must use integers from 0 (Monday) to 6 (Sunday)."
            )

        overlap = self.holidays & self.extra_working_days
        if overlap:
            raise ValueError(
                "BusinessCalendar holidays and extra working days must be disjoint."
            )

    @property
    def snapshot_ref(self) -> CalendarSnapshotRef:
        return CalendarSnapshotRef(
            calendar_ref=self.calendar_ref,
            revision=self.revision,
        )

    def is_working_day(self, local_date: date) -> bool:
        """Return whether one civil date is allowed by this exact calendar revision."""

        if local_date in self.extra_working_days:
            return True
        if local_date in self.holidays:
            return False
        return local_date.weekday() in self.working_weekdays
