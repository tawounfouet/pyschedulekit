"""LOT-14 integration tests for concurrency policy snapshots."""

from datetime import UTC, datetime

from pyschedulekit.application.scheduler_engine import SchedulerEngine
from pyschedulekit.domain.concurrency import ConcurrencyPolicy
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def test_materialized_request_keeps_original_concurrency_policy_after_reschedule() -> None:
    factory = InMemoryUnitOfWorkFactory()
    original_policy = ConcurrencyPolicy.limit(max_instances=1)
    schedule = Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=ScheduleDefinition(
            target=TargetRef.python("refresh"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(),
            ),
            concurrency=original_policy,
        ),
        reference=_instant(hour=9),
    )

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.commit()

    evaluation = SchedulerEngine(uow_factory=factory).evaluate(
        evaluation_now=_instant()
    )
    request = evaluation.requests[0]

    with factory() as uow:
        persisted = uow.schedules.get(schedule.id)
        assert persisted is not None
        persisted.reschedule(
            definition=ScheduleDefinition(
                target=TargetRef.python("refresh"),
                trigger=IntervalTrigger(
                    every=Duration.minutes(10),
                    anchor=_instant(),
                ),
                concurrency=ConcurrencyPolicy.allow(),
            ),
            reference=_instant(),
        )
        uow.schedules.save(persisted)
        uow.commit()

    with factory() as uow:
        persisted_request = uow.requests.get(request.id)
        assert persisted_request is not None
        assert persisted_request.concurrency_policy == original_policy
