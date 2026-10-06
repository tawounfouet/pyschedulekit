"""Occurrence value objects and planning services."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.domain.schedule import Schedule, ScheduleId, ScheduleRevision, ScheduleState
from pyschedulekit.domain.time import Instant


@dataclass(frozen=True, slots=True)
class OccurrenceKey:
    """Natural logical identity of one scheduled occurrence."""

    schedule_id: ScheduleId
    schedule_revision: ScheduleRevision
    scheduled_at: Instant


@dataclass(frozen=True, slots=True)
class Occurrence:
    """Immutable temporal fact produced from a Schedule definition."""

    schedule_id: ScheduleId
    schedule_revision: ScheduleRevision
    scheduled_at: Instant

    @property
    def key(self) -> OccurrenceKey:
        return OccurrenceKey(
            schedule_id=self.schedule_id,
            schedule_revision=self.schedule_revision,
            scheduled_at=self.scheduled_at,
        )


class OccurrencePlanner:
    """Pure domain service that projects Schedule timing into Occurrences."""

    def current(self, schedule: Schedule) -> Occurrence | None:
        """Return the Occurrence represented by the Schedule checkpoint.

        Non-active schedules intentionally expose no current occurrence.
        """

        if schedule.state is not ScheduleState.ACTIVE:
            return None

        scheduled_at = schedule.next_run_time
        if scheduled_at is None:
            return None

        return self._occurrence(schedule, scheduled_at)

    def next_after(self, schedule: Schedule, reference: Instant) -> Occurrence | None:
        """Calculate a future occurrence without mutating the Schedule.

        This method is useful for deterministic planning and, later, backlog
        reconstruction. It does not advance next_run_time.
        """

        if schedule.state is not ScheduleState.ACTIVE:
            return None

        scheduled_at = schedule.definition.trigger.next_after(reference)
        if scheduled_at is None:
            return None

        return self._occurrence(schedule, scheduled_at)

    @staticmethod
    def _occurrence(schedule: Schedule, scheduled_at: Instant) -> Occurrence:
        return Occurrence(
            schedule_id=schedule.id,
            schedule_revision=schedule.revision,
            scheduled_at=scheduled_at,
        )
