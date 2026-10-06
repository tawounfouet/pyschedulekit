"""LOT-06 qualification tests for Occurrence planning and identity."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.occurrence import Occurrence, OccurrenceKey, OccurrencePlanner
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleRevision,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import DateTrigger, IntervalTrigger


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _interval_schedule() -> Schedule:
    return Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=ScheduleDefinition(
            target=TargetRef.python("app.tasks:refresh"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(hour=10),
            ),
        ),
        reference=_instant(hour=9),
    )


def test_t_sch_020_occurrence_key_is_deterministic() -> None:
    key_a = OccurrenceKey(
        schedule_id=ScheduleId("schedule-1"),
        schedule_revision=ScheduleRevision(3),
        scheduled_at=_instant(hour=10),
    )
    key_b = OccurrenceKey(
        schedule_id=ScheduleId("schedule-1"),
        schedule_revision=ScheduleRevision(3),
        scheduled_at=_instant(hour=10),
    )

    assert key_a == key_b
    assert hash(key_a) == hash(key_b)


def test_t_sch_021_different_revisions_produce_different_occurrence_keys() -> None:
    key_v1 = OccurrenceKey(
        schedule_id=ScheduleId("schedule-1"),
        schedule_revision=ScheduleRevision(1),
        scheduled_at=_instant(hour=10),
    )
    key_v2 = OccurrenceKey(
        schedule_id=ScheduleId("schedule-1"),
        schedule_revision=ScheduleRevision(2),
        scheduled_at=_instant(hour=10),
    )

    assert key_v1 != key_v2


def test_t_sch_022_occurrence_scheduled_at_is_immutable() -> None:
    occurrence = Occurrence(
        schedule_id=ScheduleId("schedule-1"),
        schedule_revision=ScheduleRevision(1),
        scheduled_at=_instant(hour=10),
    )

    with pytest.raises(FrozenInstanceError):
        occurrence.scheduled_at = _instant(hour=11)  # type: ignore[misc]


def test_occurrence_key_matches_occurrence_identity() -> None:
    occurrence = Occurrence(
        schedule_id=ScheduleId("schedule-1"),
        schedule_revision=ScheduleRevision(4),
        scheduled_at=_instant(hour=10, minute=20),
    )

    assert occurrence.key == OccurrenceKey(
        schedule_id=ScheduleId("schedule-1"),
        schedule_revision=ScheduleRevision(4),
        scheduled_at=_instant(hour=10, minute=20),
    )


def test_planner_projects_current_schedule_checkpoint() -> None:
    schedule = _interval_schedule()
    planner = OccurrencePlanner()

    occurrence = planner.current(schedule)

    assert occurrence == Occurrence(
        schedule_id=ScheduleId("schedule-1"),
        schedule_revision=ScheduleRevision(1),
        scheduled_at=_instant(hour=10),
    )


def test_planner_next_after_is_pure_and_does_not_advance_schedule() -> None:
    schedule = _interval_schedule()
    planner = OccurrencePlanner()
    original_next_run_time = schedule.next_run_time
    original_persistence_version = schedule.persistence_version

    occurrence = planner.next_after(schedule, _instant(hour=10, minute=5))

    assert occurrence == Occurrence(
        schedule_id=schedule.id,
        schedule_revision=schedule.revision,
        scheduled_at=_instant(hour=10, minute=10),
    )
    assert schedule.next_run_time == original_next_run_time
    assert schedule.persistence_version == original_persistence_version


def test_paused_schedule_has_no_current_occurrence() -> None:
    schedule = _interval_schedule()
    planner = OccurrencePlanner()
    schedule.pause()

    assert planner.current(schedule) is None
    assert planner.next_after(schedule, _instant(hour=10)) is None


def test_cancelled_schedule_has_no_current_occurrence() -> None:
    schedule = _interval_schedule()
    planner = OccurrencePlanner()
    schedule.cancel()

    assert planner.current(schedule) is None


def test_completed_schedule_has_no_current_occurrence() -> None:
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=ScheduleDefinition(
            target=TargetRef.python("app.tasks:once"),
            trigger=DateTrigger(at=_instant(hour=10)),
        ),
        reference=_instant(hour=10),
    )
    planner = OccurrencePlanner()

    assert planner.current(schedule) is None
    assert planner.next_after(schedule, _instant(hour=10)) is None


def test_reschedule_changes_occurrence_key_revision_without_changing_schedule_id() -> None:
    schedule = _interval_schedule()
    planner = OccurrencePlanner()
    occurrence_v1 = planner.current(schedule)

    schedule.reschedule(
        definition=ScheduleDefinition(
            target=TargetRef.python("app.tasks:refresh"),
            trigger=IntervalTrigger(
                every=Duration.minutes(30),
                anchor=_instant(hour=10),
            ),
        ),
        reference=_instant(hour=10),
    )

    occurrence_v2 = planner.current(schedule)

    assert occurrence_v1 is not None
    assert occurrence_v2 is not None
    assert occurrence_v1.schedule_id == occurrence_v2.schedule_id
    assert occurrence_v1.schedule_revision == ScheduleRevision(1)
    assert occurrence_v2.schedule_revision == ScheduleRevision(2)
    assert occurrence_v1.key != occurrence_v2.key


def test_same_schedule_revision_and_instant_reconstruct_same_occurrence_identity() -> None:
    first = Occurrence(
        schedule_id=ScheduleId("schedule-1"),
        schedule_revision=ScheduleRevision(7),
        scheduled_at=_instant(hour=10, minute=40),
    )
    reconstructed = Occurrence(
        schedule_id=ScheduleId("schedule-1"),
        schedule_revision=ScheduleRevision(7),
        scheduled_at=_instant(hour=10, minute=40),
    )

    assert first == reconstructed
    assert first.key == reconstructed.key
