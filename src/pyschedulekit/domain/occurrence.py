"""Occurrence value objects and planning services."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.domain.calendar import BusinessCalendar
from pyschedulekit.domain.calendar_planning import CalendarOccurrencePlanner
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


@dataclass(frozen=True, slots=True)
class OccurrenceBacklog:
    """Bounded due-occurrence reconstruction from one Schedule checkpoint."""

    occurrences: tuple[Occurrence, ...]
    has_more: bool


class OccurrencePlanner:
    """Pure domain service that projects Schedule timing into valid Occurrences."""

    def __init__(
        self,
        *,
        calendar_planner: CalendarOccurrencePlanner | None = None,
    ) -> None:
        self._calendar_planner = calendar_planner or CalendarOccurrencePlanner()

    def current(
        self,
        schedule: Schedule,
        *,
        calendar: BusinessCalendar | None = None,
    ) -> Occurrence | None:
        """Return the Occurrence represented by the Schedule checkpoint.

        Non-active schedules intentionally expose no current occurrence.
        """

        if schedule.state is not ScheduleState.ACTIVE:
            return None

        scheduled_at = schedule.next_run_time
        if scheduled_at is None:
            return None

        if not self._calendar_planner.is_allowed(
            instant=scheduled_at,
            timezone=schedule.definition.timezone,
            binding=schedule.definition.calendar,
            calendar=calendar,
        ):
            return None

        return self._occurrence(schedule, scheduled_at)

    def next_after(
        self,
        schedule: Schedule,
        reference: Instant,
        *,
        calendar: BusinessCalendar | None = None,
    ) -> Occurrence | None:
        """Calculate a future occurrence without mutating the Schedule.

        This method is useful for deterministic planning and, later, backlog
        reconstruction. It does not advance next_run_time.
        """

        if schedule.state is not ScheduleState.ACTIVE:
            return None

        scheduled_at = self._calendar_planner.next_after(
            trigger=schedule.definition.trigger,
            reference=reference,
            timezone=schedule.definition.timezone,
            binding=schedule.definition.calendar,
            calendar=calendar,
        )
        if scheduled_at is None:
            return None

        return self._occurrence(schedule, scheduled_at)

    def due_backlog(
        self,
        schedule: Schedule,
        *,
        until: Instant,
        limit: int,
        calendar: BusinessCalendar | None = None,
    ) -> OccurrenceBacklog:
        """Reconstruct due occurrences oldest-first with bounded work.

        At most limit occurrences are returned. One extra Trigger lookup is
        used to determine whether more due work exists beyond the returned batch.
        """

        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        current = self.current(schedule, calendar=calendar)
        if current is None or current.scheduled_at > until:
            return OccurrenceBacklog(occurrences=(), has_more=False)

        occurrences: list[Occurrence] = [current]
        last = current

        while len(occurrences) < limit:
            next_occurrence = self.next_after(
                schedule,
                last.scheduled_at,
                calendar=calendar,
            )
            if next_occurrence is None or next_occurrence.scheduled_at > until:
                return OccurrenceBacklog(
                    occurrences=tuple(occurrences),
                    has_more=False,
                )
            occurrences.append(next_occurrence)
            last = next_occurrence

        next_occurrence = self.next_after(
            schedule,
            last.scheduled_at,
            calendar=calendar,
        )
        has_more = next_occurrence is not None and next_occurrence.scheduled_at <= until
        return OccurrenceBacklog(
            occurrences=tuple(occurrences),
            has_more=has_more,
        )

    @staticmethod
    def _occurrence(schedule: Schedule, scheduled_at: Instant) -> Occurrence:
        return Occurrence(
            schedule_id=schedule.id,
            schedule_revision=schedule.revision,
            scheduled_at=scheduled_at,
        )
