"""CMP-01 qualification for AnyOfTrigger occurrence planning."""

from datetime import UTC, date, datetime

from pyschedulekit.domain.calendar import BusinessCalendar, CalendarRef, CalendarRevision
from pyschedulekit.domain.occurrence import OccurrencePlanner
from pyschedulekit.domain.schedule import (
    PersistenceVersion,
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleState,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import AnyOfTrigger, DateTrigger, IntervalTrigger


def _instant(day: int = 1, hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, day, hour, minute, tzinfo=UTC))


def _recurring_schedule() -> Schedule:
    return Schedule.create(
        schedule_id=ScheduleId("composite-schedule"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:composite"),
            trigger=AnyOfTrigger(
                IntervalTrigger(
                    every=Duration.minutes(10),
                    anchor=_instant(),
                ),
                IntervalTrigger(
                    every=Duration.minutes(15),
                    anchor=_instant(),
                ),
            ),
        ),
        reference=_instant(hour=9, minute=59),
    )


def test_schedule_initializes_from_earliest_composite_candidate() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("finite-composite"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:composite"),
            trigger=AnyOfTrigger(
                DateTrigger(at=_instant(hour=12)),
                DateTrigger(at=_instant(hour=10)),
            ),
        ),
        reference=_instant(hour=9),
    )

    assert schedule.state is ScheduleState.ACTIVE
    assert schedule.next_run_time == _instant(hour=10)


def test_schedule_checkpoint_advances_through_unique_union_candidates() -> None:
    schedule = _recurring_schedule()

    expected = (
        _instant(minute=10),
        _instant(minute=15),
        _instant(minute=20),
        _instant(minute=30),
        _instant(minute=40),
    )
    reference = _instant()

    for candidate in expected:
        assert schedule.advance_next_run_after(reference=reference) == candidate
        reference = candidate

    assert schedule.persistence_version == PersistenceVersion(len(expected))
    assert schedule.state is ScheduleState.ACTIVE


def test_occurrence_backlog_merges_children_oldest_first_without_duplicates() -> None:
    schedule = _recurring_schedule()

    backlog = OccurrencePlanner().due_backlog(
        schedule,
        until=_instant(minute=30),
        limit=10,
    )

    assert [occurrence.scheduled_at for occurrence in backlog.occurrences] == [
        _instant(),
        _instant(minute=10),
        _instant(minute=15),
        _instant(minute=20),
        _instant(minute=30),
    ]
    assert backlog.has_more is False
    assert schedule.next_run_time == _instant()
    assert schedule.persistence_version == PersistenceVersion(0)


def test_occurrence_planner_remains_pure_for_composite_schedule() -> None:
    schedule = _recurring_schedule()

    occurrence = OccurrencePlanner().next_after(
        schedule,
        _instant(minute=12),
    )

    assert occurrence is not None
    assert occurrence.scheduled_at == _instant(minute=15)
    assert schedule.next_run_time == _instant()
    assert schedule.persistence_version == PersistenceVersion(0)


def test_finite_composite_completes_only_after_every_child_is_exhausted() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("finite-composite"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:composite"),
            trigger=AnyOfTrigger(
                DateTrigger(at=_instant(hour=10)),
                DateTrigger(at=_instant(hour=12)),
            ),
        ),
        reference=_instant(hour=9),
    )

    assert schedule.advance_next_run_after(reference=_instant(hour=10)) == _instant(hour=12)
    assert schedule.advance_next_run_after(reference=_instant(hour=12)) is None
    assert schedule.state is ScheduleState.COMPLETED
    assert schedule.next_run_time is None


def test_calendar_bound_composite_skips_excluded_earliest_candidate() -> None:
    calendar = BusinessCalendar(
        calendar_ref=CalendarRef("business-days"),
        revision=CalendarRevision(1),
        holidays=frozenset({date(2026, 1, 3)}),
    )
    schedule = Schedule.create(
        schedule_id=ScheduleId("calendar-composite"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:composite"),
            trigger=AnyOfTrigger(
                DateTrigger(at=_instant(day=3)),
                DateTrigger(at=_instant(day=5)),
            ),
            calendar=calendar.snapshot_ref,
        ),
        reference=_instant(day=2, hour=12),
        calendar=calendar,
    )

    assert schedule.next_run_time == _instant(day=5)
