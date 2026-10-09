"""Pure calendar-aware trigger candidate planning."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.domain.calendar import (
    BusinessCalendar,
    CalendarSnapshotRef,
)
from pyschedulekit.domain.time import Instant, Timezone
from pyschedulekit.domain.trigger import CalendarAwareTrigger, Trigger


class CalendarBindingError(ValueError):
    """Raised when a resolved calendar does not match a Schedule binding."""


class CalendarPlanningLimitExceededError(RuntimeError):
    """Raised when calendar filtering cannot find a valid candidate boundedly."""


@dataclass(frozen=True, slots=True)
class CalendarOccurrencePlanner:
    """Filter Trigger candidates through an exact immutable BusinessCalendar."""

    max_candidates: int = 10_000

    def __post_init__(self) -> None:
        if self.max_candidates < 1:
            raise ValueError("max_candidates must be greater than or equal to 1.")

    def is_allowed(
        self,
        *,
        instant: Instant,
        timezone: Timezone,
        binding: CalendarSnapshotRef | None,
        calendar: BusinessCalendar | None,
    ) -> bool:
        """Return whether one candidate Instant is valid for the Schedule calendar."""

        resolved = self._validate_binding(binding=binding, calendar=calendar)
        if resolved is None:
            return True
        return resolved.is_working_day(timezone.to_local(instant).date())

    def next_after(
        self,
        *,
        trigger: Trigger | CalendarAwareTrigger,
        reference: Instant,
        timezone: Timezone,
        binding: CalendarSnapshotRef | None,
        calendar: BusinessCalendar | None,
    ) -> Instant | None:
        """Return the first Trigger candidate accepted by the bound calendar."""

        resolved = self._validate_binding(binding=binding, calendar=calendar)

        if isinstance(trigger, CalendarAwareTrigger):
            if resolved is None:
                raise CalendarBindingError(
                    "A calendar-aware Trigger requires a Schedule calendar binding."
                )
            return trigger.next_after_with_calendar(
                reference,
                timezone=timezone,
                calendar=resolved,
            )

        cursor = reference
        for _ in range(self.max_candidates):
            candidate = trigger.next_after(cursor)
            if candidate is None:
                return None
            if resolved is None or resolved.is_working_day(timezone.to_local(candidate).date()):
                return candidate
            cursor = candidate

        raise CalendarPlanningLimitExceededError(
            "Calendar-aware occurrence planning exceeded the configured candidate limit."
        )

    @staticmethod
    def _validate_binding(
        *,
        binding: CalendarSnapshotRef | None,
        calendar: BusinessCalendar | None,
    ) -> BusinessCalendar | None:
        if binding is None:
            if calendar is not None:
                raise CalendarBindingError(
                    "An unbound Schedule must not receive a resolved BusinessCalendar."
                )
            return None

        if calendar is None:
            raise CalendarBindingError(
                "A calendar-bound Schedule requires its exact BusinessCalendar revision."
            )

        if calendar.snapshot_ref != binding:
            raise CalendarBindingError(
                "Resolved BusinessCalendar does not match the Schedule calendar binding."
            )

        return calendar
