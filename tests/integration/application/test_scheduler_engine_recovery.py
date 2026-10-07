"""LOT-13 integration tests for bounded catch-up and coalescing."""

from datetime import UTC, datetime

from pyschedulekit.application.scheduler_engine import SchedulerEngine
from pyschedulekit.domain.execution_request import ExecutionRequest
from pyschedulekit.domain.misfire import MisfirePolicy, MisfirePolicyAction
from pyschedulekit.domain.occurrence import OccurrencePlanner
from pyschedulekit.domain.schedule import (
    PersistenceVersion,
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, GracePeriod, Instant
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory


def _instant(minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, minute, tzinfo=UTC))


def _schedule(*, policy: MisfirePolicy) -> Schedule:
    return Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=ScheduleDefinition(
            target=TargetRef.python("refresh"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(),
            ),
            misfire=policy,
        ),
        reference=Instant(datetime(2026, 1, 1, 9, 0, tzinfo=UTC)),
    )


def _persist(factory: InMemoryUnitOfWorkFactory, schedule: Schedule) -> None:
    with factory() as uow:
        uow.schedules.add(schedule)
        uow.commit()


def _load(factory: InMemoryUnitOfWorkFactory) -> Schedule:
    with factory() as uow:
        schedule = uow.schedules.get(ScheduleId("schedule-1"))
        assert schedule is not None
        return schedule


def test_t_rec_001_catch_up_materializes_bounded_oldest_first_batch() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(factory, _schedule(policy=MisfirePolicy.catch_up(max_occurrences=3)))

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(minute=35))

    assert [request.occurrence_key.scheduled_at for request in result.requests] == [
        _instant(),
        _instant(minute=10),
        _instant(minute=20),
    ]
    assert result.recovery_limit_schedules == ()
    assert len(result.recovery_records) == 1
    record = result.recovery_records[0]
    assert record.action is MisfirePolicyAction.CATCH_UP
    assert record.has_more
    assert record.materialized_occurrence_keys == tuple(
        request.occurrence_key for request in result.requests
    )

    committed = _load(factory)
    assert committed.next_run_time == _instant(minute=30)
    assert committed.persistence_version == PersistenceVersion(3)


def test_t_rec_002_catch_up_continues_backlog_on_next_cycle() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(factory, _schedule(policy=MisfirePolicy.catch_up(max_occurrences=3)))
    engine = SchedulerEngine(uow_factory=factory)

    first = engine.evaluate(evaluation_now=_instant(minute=35))
    second = engine.evaluate(evaluation_now=_instant(minute=35))

    assert len(first.requests) == 3
    assert [request.occurrence_key.scheduled_at for request in second.requests] == [
        _instant(minute=30)
    ]
    assert not second.recovery_records[0].has_more

    committed = _load(factory)
    assert committed.next_run_time == _instant(minute=40)


def test_t_rec_003_coalesce_materializes_only_latest_due_occurrence() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(factory, _schedule(policy=MisfirePolicy.coalesce(max_occurrences=10)))

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(minute=35))

    assert [request.occurrence_key.scheduled_at for request in result.requests] == [
        _instant(minute=30)
    ]
    record = result.recovery_records[0]
    assert record.action is MisfirePolicyAction.COALESCE
    assert [key.scheduled_at for key in record.considered_occurrence_keys] == [
        _instant(),
        _instant(minute=10),
        _instant(minute=20),
        _instant(minute=30),
    ]
    assert [key.scheduled_at for key in record.materialized_occurrence_keys] == [
        _instant(minute=30)
    ]
    assert not record.has_more

    committed = _load(factory)
    assert committed.next_run_time == _instant(minute=40)
    assert committed.persistence_version == PersistenceVersion(4)


def test_t_rec_004_coalesce_fails_closed_when_scan_limit_is_exceeded() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(factory, _schedule(policy=MisfirePolicy.coalesce(max_occurrences=3)))

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(minute=35))

    assert result.requests == ()
    assert result.recovery_limit_schedules == (ScheduleId("schedule-1"),)
    record = result.recovery_records[0]
    assert record.has_more
    assert [key.scheduled_at for key in record.considered_occurrence_keys] == [
        _instant(),
        _instant(minute=10),
        _instant(minute=20),
    ]

    committed = _load(factory)
    assert committed.next_run_time == _instant()
    assert committed.persistence_version == PersistenceVersion(0)


def test_t_rec_005_coalesce_preserves_preexisting_durable_intent() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _schedule(policy=MisfirePolicy.coalesce(max_occurrences=10))
    current = OccurrencePlanner().current(schedule)
    assert current is not None
    _persist(factory, schedule)

    existing = ExecutionRequest.from_occurrence(
        occurrence=current,
        target=schedule.definition.target,
        created_at=_instant(),
    )
    with factory() as uow:
        uow.requests.add(existing)
        uow.commit()

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(minute=35))

    assert [request.occurrence_key.scheduled_at for request in result.requests] == [
        _instant(),
        _instant(minute=30),
    ]
    assert result.requests[0] == existing

    committed = _load(factory)
    assert committed.next_run_time == _instant(minute=40)


def test_t_rec_006_catch_up_reuses_existing_request_and_creates_missing_ones() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _schedule(policy=MisfirePolicy.catch_up(max_occurrences=4))
    current = OccurrencePlanner().current(schedule)
    assert current is not None
    _persist(factory, schedule)

    existing = ExecutionRequest.from_occurrence(
        occurrence=current,
        target=schedule.definition.target,
        created_at=_instant(),
    )
    with factory() as uow:
        uow.requests.add(existing)
        uow.commit()

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(minute=35))

    assert len(result.requests) == 4
    assert result.requests[0] == existing
    assert [request.occurrence_key.scheduled_at for request in result.requests] == [
        _instant(),
        _instant(minute=10),
        _instant(minute=20),
        _instant(minute=30),
    ]


def test_t_rec_007_advanced_policy_does_not_expand_backlog_inside_grace() -> None:
    factory = InMemoryUnitOfWorkFactory()
    policy = MisfirePolicy.catch_up(
        grace=GracePeriod(Duration.minutes(10)),
        max_occurrences=10,
    )
    schedule = _schedule(policy=policy)
    _persist(factory, schedule)

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(minute=5))

    assert len(result.requests) == 1
    assert result.recovery_records == ()
    assert _load(factory).next_run_time == _instant(minute=10)
