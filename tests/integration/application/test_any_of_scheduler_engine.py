"""CMP-02 SchedulerEngine qualification for composite checkpoints and bounds."""

from datetime import UTC, datetime

from pyschedulekit.application.scheduler_engine import SchedulerEngine
from pyschedulekit.domain.misfire import MisfirePolicy
from pyschedulekit.domain.schedule import Schedule, ScheduleDefinition, ScheduleId, TargetRef
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import AnyOfTrigger, IntervalTrigger
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory


def _instant(minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, minute, tzinfo=UTC))


def _schedule(*, misfire: MisfirePolicy | None = None) -> Schedule:
    return Schedule.create(
        schedule_id=ScheduleId("composite"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:composite"),
            trigger=AnyOfTrigger(
                IntervalTrigger(every=Duration.minutes(10), anchor=_instant()),
                IntervalTrigger(every=Duration.minutes(15), anchor=_instant()),
            ),
            misfire=misfire or MisfirePolicy.run_now(),
        ),
        reference=Instant(datetime(2026, 1, 1, 9, 59, tzinfo=UTC)),
    )


def _persist(factory: InMemoryUnitOfWorkFactory, schedule: Schedule) -> None:
    with factory() as uow:
        uow.schedules.add(schedule)
        uow.commit()


def _load(factory: InMemoryUnitOfWorkFactory) -> Schedule:
    with factory() as uow:
        schedule = uow.schedules.get(ScheduleId("composite"))
        assert schedule is not None
        return schedule


def test_shared_child_instant_materializes_one_request_and_one_checkpoint_advance() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(factory, _schedule())

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant())

    assert [request.occurrence_key.scheduled_at for request in result.requests] == [_instant()]
    assert _load(factory).next_run_time == _instant(10)


def test_catch_up_materializes_unique_ordered_union_and_advances_checkpoint() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(factory, _schedule(misfire=MisfirePolicy.catch_up()))

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(30))

    assert [request.occurrence_key.scheduled_at for request in result.requests] == [
        _instant(),
        _instant(10),
        _instant(15),
        _instant(20),
        _instant(30),
    ]
    assert _load(factory).next_run_time == _instant(40)
    assert result.recovery_limit_schedules == ()


def test_catch_up_respects_max_occurrences_for_composite_backlog() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(
        factory,
        _schedule(misfire=MisfirePolicy.catch_up(max_occurrences=4)),
    )

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(30))

    assert [request.occurrence_key.scheduled_at for request in result.requests] == [
        _instant(),
        _instant(10),
        _instant(15),
        _instant(20),
    ]
    assert result.recovery_records[0].has_more
    assert result.recovery_limit_schedules == ()
    assert _load(factory).next_run_time == _instant(30)


def test_coalesce_materializes_latest_unique_union_candidate() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(factory, _schedule(misfire=MisfirePolicy.coalesce()))

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(30))

    assert [request.occurrence_key.scheduled_at for request in result.requests] == [_instant(30)]
    assert [key.scheduled_at for key in result.recovery_records[0].considered_occurrence_keys] == [
        _instant(),
        _instant(10),
        _instant(15),
        _instant(20),
        _instant(30),
    ]
    assert _load(factory).next_run_time == _instant(40)


def test_bounded_coalesce_reports_limit_without_advancing_checkpoint() -> None:
    factory = InMemoryUnitOfWorkFactory()
    _persist(
        factory,
        _schedule(misfire=MisfirePolicy.coalesce(max_occurrences=4)),
    )

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(30))

    assert result.requests == ()
    assert result.recovery_records[0].has_more
    assert result.recovery_limit_schedules == (ScheduleId("composite"),)
    assert _load(factory).next_run_time == _instant()
