"""LOT-08 integration tests for SchedulerEngine evaluation semantics."""

from datetime import UTC, datetime

import pytest

from pyschedulekit.application.scheduler_engine import SchedulerEngine
from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.occurrence import Occurrence, OccurrenceKey, OccurrencePlanner
from pyschedulekit.domain.schedule import (
    PersistenceVersion,
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleRevision,
    ScheduleState,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import DateTrigger, IntervalTrigger
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _interval_schedule(
    schedule_id: str,
    *,
    target: str | None = None,
    anchor_hour: int = 10,
    anchor_minute: int = 0,
) -> Schedule:
    return Schedule.create(
        schedule_id=ScheduleId(schedule_id),
        definition=ScheduleDefinition(
            target=TargetRef.python(target or f"app.tasks:{schedule_id}"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(anchor_hour, anchor_minute),
            ),
        ),
        reference=_instant(hour=9),
    )


def _persist_schedule(factory: InMemoryUnitOfWorkFactory, schedule: Schedule) -> None:
    with factory() as uow:
        uow.schedules.add(schedule)
        uow.commit()


def _load_schedule(factory: InMemoryUnitOfWorkFactory, schedule_id: str) -> Schedule:
    with factory() as uow:
        schedule = uow.schedules.get(ScheduleId(schedule_id))
        assert schedule is not None
        return schedule


def test_request_id_is_deterministic_for_same_occurrence() -> None:
    key = OccurrenceKey(
        schedule_id=ScheduleId("schedule-1"),
        schedule_revision=ScheduleRevision(1),
        scheduled_at=_instant(),
    )

    assert RequestId.for_occurrence(key) == RequestId.for_occurrence(key)


def test_request_id_changes_when_occurrence_revision_changes() -> None:
    key_v1 = OccurrenceKey(
        schedule_id=ScheduleId("schedule-1"),
        schedule_revision=ScheduleRevision(1),
        scheduled_at=_instant(),
    )
    key_v2 = OccurrenceKey(
        schedule_id=ScheduleId("schedule-1"),
        schedule_revision=ScheduleRevision(2),
        scheduled_at=_instant(),
    )

    assert RequestId.for_occurrence(key_v1) != RequestId.for_occurrence(key_v2)


def test_execution_request_identity_and_payload_are_read_only() -> None:
    occurrence = Occurrence(
        schedule_id=ScheduleId("schedule-1"),
        schedule_revision=ScheduleRevision(1),
        scheduled_at=_instant(),
    )
    request = ExecutionRequest.from_occurrence(
        occurrence=occurrence,
        target=TargetRef.python("app.tasks:refresh"),
        created_at=_instant(),
    )

    with pytest.raises(AttributeError):
        request.target = TargetRef.python("other")  # type: ignore[misc]


def test_t_run_001_no_due_schedule_produces_no_request() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist_schedule(factory, _interval_schedule("schedule-1", anchor_hour=11))
    engine = SchedulerEngine(uow_factory=factory)

    result = engine.evaluate(evaluation_now=_instant(hour=10))

    assert result.requests == ()
    assert result.conflicts == ()
    schedule = _load_schedule(factory, "schedule-1")
    assert schedule.next_run_time == _instant(hour=11)
    assert schedule.persistence_version == PersistenceVersion(0)


def test_t_run_002_due_schedule_materializes_request_and_advances_checkpoint() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist_schedule(factory, _interval_schedule("schedule-1"))
    engine = SchedulerEngine(uow_factory=factory)

    result = engine.evaluate(evaluation_now=_instant(hour=10))

    assert len(result.requests) == 1
    request = result.requests[0]
    assert request.occurrence_key == OccurrenceKey(
        schedule_id=ScheduleId("schedule-1"),
        schedule_revision=ScheduleRevision(1),
        scheduled_at=_instant(hour=10),
    )
    assert request.target == TargetRef.python("app.tasks:schedule-1")
    assert request.created_at == _instant(hour=10)

    schedule = _load_schedule(factory, "schedule-1")
    assert schedule.next_run_time == _instant(hour=10, minute=10)
    assert schedule.persistence_version == PersistenceVersion(1)


def test_t_run_003_same_evaluation_now_is_used_for_all_materialized_requests() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist_schedule(factory, _interval_schedule("schedule-a"))
    _persist_schedule(factory, _interval_schedule("schedule-b"))
    engine = SchedulerEngine(uow_factory=factory)
    evaluation_now = _instant(hour=10, minute=3)

    result = engine.evaluate(evaluation_now=evaluation_now)

    assert len(result.requests) == 2
    assert {request.created_at for request in result.requests} == {evaluation_now}


def test_t_run_004_engine_materializes_one_overdue_occurrence_per_schedule_per_cycle() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist_schedule(factory, _interval_schedule("schedule-1"))
    engine = SchedulerEngine(uow_factory=factory)
    evaluation_now = _instant(hour=10, minute=35)

    first = engine.evaluate(evaluation_now=evaluation_now)
    second = engine.evaluate(evaluation_now=evaluation_now)

    assert first.requests[0].occurrence_key.scheduled_at == _instant(hour=10)
    assert second.requests[0].occurrence_key.scheduled_at == _instant(hour=10, minute=10)

    schedule = _load_schedule(factory, "schedule-1")
    assert schedule.next_run_time == _instant(hour=10, minute=20)


def test_t_run_005_finite_trigger_materializes_then_completes_schedule() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = Schedule.create(
        schedule_id=ScheduleId("once"),
        definition=ScheduleDefinition(
            target=TargetRef.python("app.tasks:once"),
            trigger=DateTrigger(at=_instant(hour=10)),
        ),
        reference=_instant(hour=9),
    )
    _persist_schedule(factory, schedule)
    engine = SchedulerEngine(uow_factory=factory)

    result = engine.evaluate(evaluation_now=_instant(hour=10))

    assert len(result.requests) == 1
    committed = _load_schedule(factory, "once")
    assert committed.state is ScheduleState.COMPLETED
    assert committed.next_run_time is None
    assert committed.persistence_version == PersistenceVersion(1)


def test_request_target_is_a_snapshot_of_schedule_definition_at_materialization() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist_schedule(
        factory,
        _interval_schedule("schedule-1", target="app.tasks:old"),
    )
    engine = SchedulerEngine(uow_factory=factory)

    first = engine.evaluate(evaluation_now=_instant(hour=10))
    request = first.requests[0]

    with factory() as uow:
        schedule = uow.schedules.get(ScheduleId("schedule-1"))
        assert schedule is not None
        schedule.reschedule(
            definition=ScheduleDefinition(
                target=TargetRef.python("app.tasks:new"),
                trigger=IntervalTrigger(
                    every=Duration.minutes(10),
                    anchor=_instant(hour=10),
                ),
            ),
            reference=_instant(hour=10),
        )
        uow.schedules.save(schedule)
        uow.commit()

    assert request.target == TargetRef.python("app.tasks:old")


def test_existing_request_repairs_checkpoint_without_creating_duplicate() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _interval_schedule("schedule-1")
    _persist_schedule(factory, schedule)

    occurrence = OccurrencePlanner().current(schedule)
    assert occurrence is not None
    preexisting = ExecutionRequest.from_occurrence(
        occurrence=occurrence,
        target=schedule.definition.target,
        created_at=_instant(hour=9, minute=59),
    )

    with factory() as uow:
        uow.requests.add(preexisting)
        uow.commit()

    engine = SchedulerEngine(uow_factory=factory)
    result = engine.evaluate(evaluation_now=_instant(hour=10))

    assert result.requests == (preexisting,)
    committed = _load_schedule(factory, "schedule-1")
    assert committed.next_run_time == _instant(hour=10, minute=10)

    with factory() as uow:
        assert uow.requests.get_by_occurrence(occurrence.key) == preexisting


def test_request_commit_conflict_does_not_advance_schedule_checkpoint() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _interval_schedule("schedule-1")
    _persist_schedule(factory, schedule)

    occurrence = OccurrencePlanner().current(schedule)
    assert occurrence is not None
    expected_id = RequestId.for_occurrence(occurrence.key)
    collision_key = OccurrenceKey(
        schedule_id=ScheduleId("other"),
        schedule_revision=ScheduleRevision(1),
        scheduled_at=_instant(hour=10),
    )
    collision = ExecutionRequest(
        id=expected_id,
        occurrence_key=collision_key,
        target=TargetRef.python("app.tasks:collision"),
        created_at=_instant(hour=9),
    )

    with factory() as uow:
        uow.requests.add(collision)
        uow.commit()

    engine = SchedulerEngine(uow_factory=factory)
    result = engine.evaluate(evaluation_now=_instant(hour=10))

    assert result.requests == ()
    assert result.conflicts == (ScheduleId("schedule-1"),)

    committed = _load_schedule(factory, "schedule-1")
    assert committed.next_run_time == _instant(hour=10)
    assert committed.persistence_version == PersistenceVersion(0)

    with factory() as uow:
        assert uow.requests.get_by_occurrence(occurrence.key) is None


def test_conflict_on_one_schedule_does_not_block_another_schedule() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule_a = _interval_schedule("schedule-a")
    schedule_b = _interval_schedule("schedule-b")
    _persist_schedule(factory, schedule_a)
    _persist_schedule(factory, schedule_b)

    occurrence_a = OccurrencePlanner().current(schedule_a)
    assert occurrence_a is not None
    collision = ExecutionRequest(
        id=RequestId.for_occurrence(occurrence_a.key),
        occurrence_key=OccurrenceKey(
            schedule_id=ScheduleId("collision"),
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(hour=10),
        ),
        target=TargetRef.python("app.tasks:collision"),
        created_at=_instant(hour=9),
    )
    with factory() as uow:
        uow.requests.add(collision)
        uow.commit()

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(hour=10))

    assert result.conflicts == (ScheduleId("schedule-a"),)
    assert [request.occurrence_key.schedule_id for request in result.requests] == [
        ScheduleId("schedule-b")
    ]

    committed_a = _load_schedule(factory, "schedule-a")
    committed_b = _load_schedule(factory, "schedule-b")
    assert committed_a.next_run_time == _instant(hour=10)
    assert committed_b.next_run_time == _instant(hour=10, minute=10)


def test_limit_applies_to_deterministic_due_schedule_discovery() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist_schedule(factory, _interval_schedule("schedule-b"))
    _persist_schedule(factory, _interval_schedule("schedule-a"))
    _persist_schedule(factory, _interval_schedule("schedule-c"))
    engine = SchedulerEngine(uow_factory=factory)

    result = engine.evaluate(
        evaluation_now=_instant(hour=10),
        limit=2,
    )

    assert [request.occurrence_key.schedule_id.value for request in result.requests] == [
        "schedule-a",
        "schedule-b",
    ]
    untouched = _load_schedule(factory, "schedule-c")
    assert untouched.next_run_time == _instant(hour=10)


def test_engine_rejects_non_positive_limit() -> None:
    engine = SchedulerEngine(uow_factory=InMemoryUnitOfWorkFactory())

    with pytest.raises(ValueError, match="limit"):
        engine.evaluate(evaluation_now=_instant(hour=10), limit=0)
