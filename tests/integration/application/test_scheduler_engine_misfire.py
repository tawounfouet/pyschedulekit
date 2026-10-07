"""LOT-12 integration tests for SchedulerEngine misfire behavior."""

from datetime import UTC, datetime

from pyschedulekit.application.scheduler_engine import SchedulerEngine
from pyschedulekit.domain.execution_request import ExecutionRequest
from pyschedulekit.domain.misfire import (
    LatenessStatus,
    MisfireDecisionAction,
    MisfirePolicy,
)
from pyschedulekit.domain.occurrence import OccurrencePlanner
from pyschedulekit.domain.schedule import (
    PersistenceVersion,
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleState,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, GracePeriod, Instant
from pyschedulekit.domain.triggers import DateTrigger, IntervalTrigger
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory


def _instant(minute: int = 0, second: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, minute, second, tzinfo=UTC))


def _interval_schedule(
    *,
    policy: MisfirePolicy,
    schedule_id: str = "schedule-1",
) -> Schedule:
    return Schedule.create(
        schedule_id=ScheduleId(schedule_id),
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


def _load(factory: InMemoryUnitOfWorkFactory, schedule_id: str = "schedule-1") -> Schedule:
    with factory() as uow:
        schedule = uow.schedules.get(ScheduleId(schedule_id))
        assert schedule is not None
        return schedule


def test_t_mis_020_default_run_now_preserves_pre_misfire_engine_behavior() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _interval_schedule(policy=MisfirePolicy.run_now())
    _persist(factory, schedule)

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(minute=35))

    assert len(result.requests) == 1
    assert result.requests[0].occurrence_key.scheduled_at == _instant()
    assert result.requests[0].created_at == _instant(minute=35)
    assert result.misfire_decisions[0].decision.is_misfire
    assert result.misfire_decisions[0].decision.action is MisfireDecisionAction.MATERIALIZE

    committed = _load(factory)
    assert committed.next_run_time == _instant(minute=10)


def test_t_mis_021_skip_policy_advances_without_creating_request() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _interval_schedule(policy=MisfirePolicy.skip())
    _persist(factory, schedule)

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(minute=35))

    assert result.requests == ()
    assert len(result.misfire_decisions) == 1
    decision = result.misfire_decisions[0].decision
    assert decision.classification.status is LatenessStatus.MISFIRED
    assert decision.action is MisfireDecisionAction.SKIP

    committed = _load(factory)
    assert committed.next_run_time == _instant(minute=10)
    assert committed.persistence_version == PersistenceVersion(1)


def test_t_mis_022_skip_policy_materializes_when_late_but_inside_grace() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _interval_schedule(policy=MisfirePolicy.skip(grace=GracePeriod.seconds(60)))
    _persist(factory, schedule)

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(second=30))

    assert len(result.requests) == 1
    decision = result.misfire_decisions[0].decision
    assert decision.classification.status is LatenessStatus.LATE_ELIGIBLE
    assert decision.action is MisfireDecisionAction.MATERIALIZE


def test_t_mis_023_skip_policy_materializes_exactly_at_grace_deadline() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _interval_schedule(policy=MisfirePolicy.skip(grace=GracePeriod.seconds(60)))
    _persist(factory, schedule)

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(minute=1))

    assert len(result.requests) == 1
    assert (
        result.misfire_decisions[0].decision.classification.status is LatenessStatus.LATE_ELIGIBLE
    )


def test_t_mis_024_skip_policy_skips_strictly_after_grace_deadline() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _interval_schedule(policy=MisfirePolicy.skip(grace=GracePeriod.seconds(60)))
    _persist(factory, schedule)

    result = SchedulerEngine(uow_factory=factory).evaluate(
        evaluation_now=_instant(minute=1, second=1)
    )

    assert result.requests == ()
    assert result.misfire_decisions[0].decision.action is MisfireDecisionAction.SKIP


def test_t_mis_025_run_now_preserves_original_occurrence_identity() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _interval_schedule(policy=MisfirePolicy.run_now(grace=GracePeriod.seconds(30)))
    original = OccurrencePlanner().current(schedule)
    assert original is not None
    _persist(factory, schedule)

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(minute=5))

    assert len(result.requests) == 1
    request = result.requests[0]
    assert request.occurrence_key == original.key
    assert request.created_at == _instant(minute=5)


def test_t_mis_026_skipped_finite_date_trigger_completes_schedule() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = Schedule.create(
        schedule_id=ScheduleId("once"),
        definition=ScheduleDefinition(
            target=TargetRef.python("once"),
            trigger=DateTrigger(at=_instant()),
            misfire=MisfirePolicy.skip(),
        ),
        reference=Instant(datetime(2026, 1, 1, 9, 0, tzinfo=UTC)),
    )
    _persist(factory, schedule)

    result = SchedulerEngine(uow_factory=factory).evaluate(
        evaluation_now=_instant(minute=5)
    )

    assert result.requests == ()
    committed = _load(factory, "once")
    assert committed.state is ScheduleState.COMPLETED
    assert committed.next_run_time is None


def test_t_mis_027_existing_durable_request_wins_over_later_skip_policy() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _interval_schedule(policy=MisfirePolicy.skip())
    occurrence = OccurrencePlanner().current(schedule)
    assert occurrence is not None
    _persist(factory, schedule)

    preexisting = ExecutionRequest.from_occurrence(
        occurrence=occurrence,
        target=schedule.definition.target,
        created_at=_instant(),
    )
    with factory() as uow:
        uow.requests.add(preexisting)
        uow.commit()

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(minute=35))

    assert result.requests == (preexisting,)
    assert result.misfire_decisions == ()
    committed = _load(factory)
    assert committed.next_run_time == _instant(minute=10)


def test_t_mis_028_catch_up_isolated_without_mutating_schedule() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _interval_schedule(policy=MisfirePolicy.catch_up())
    _persist(factory, schedule)

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(minute=35))

    assert result.requests == ()
    assert result.unsupported_policy_schedules == (ScheduleId("schedule-1"),)
    assert result.misfire_decisions[0].decision.action is MisfireDecisionAction.CATCH_UP

    committed = _load(factory)
    assert committed.next_run_time == _instant()
    assert committed.persistence_version == PersistenceVersion(0)


def test_t_mis_029_coalesce_isolated_without_mutating_schedule() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _interval_schedule(policy=MisfirePolicy.coalesce())
    _persist(factory, schedule)

    result = SchedulerEngine(uow_factory=factory).evaluate(evaluation_now=_instant(minute=35))

    assert result.requests == ()
    assert result.unsupported_policy_schedules == (ScheduleId("schedule-1"),)
    assert result.misfire_decisions[0].decision.action is MisfireDecisionAction.COALESCE

    committed = _load(factory)
    assert committed.next_run_time == _instant()
