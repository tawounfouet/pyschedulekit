"""Resolve exact Schedule calendar bindings at the application boundary."""

from __future__ import annotations

from pyschedulekit.domain.calendar import BusinessCalendar, CalendarSnapshotRef
from pyschedulekit.errors import PyScheduleKitConfigurationError
from pyschedulekit.ports.calendar import CalendarProvider


def resolve_calendar_binding(
    binding: CalendarSnapshotRef | None,
    provider: CalendarProvider | None,
) -> BusinessCalendar | None:
    """Resolve one exact immutable calendar revision or fail closed."""

    if binding is None:
        return None

    if provider is None:
        raise PyScheduleKitConfigurationError(
            "A calendar-bound Schedule requires a configured CalendarProvider."
        )

    calendar = provider.resolve(
        binding.calendar_ref,
        revision=binding.revision,
    )
    if calendar.snapshot_ref != binding:
        raise PyScheduleKitConfigurationError(
            "CalendarProvider returned a revision that does not match the Schedule binding."
        )
    return calendar
