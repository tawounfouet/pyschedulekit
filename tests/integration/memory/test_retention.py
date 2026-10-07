"""LOT-32 in-memory retention safety qualification."""

from datetime import UTC, datetime

from pyschedulekit import Duration, Instant, RetentionPolicy, Scheduler
from pyschedulekit.domain.execution import Execution
from pyschedulekit.domain.execution_request import ExecutionRequest
from pyschedulekit.domain.occurrence import Occurrence
from pyschedulekit.domain.schedule import Schedule, ScheduleDefinition, ScheduleId, TargetRef
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.testing import MutableClock


def _instant() -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))


def test_t_retention_memory_001_non_terminal_execution_graph_is_never_deleted() -> None:
    clock = MutableClock(_instant())
    factory = InMemoryUnitOfWorkFactory()
    schedule = Schedule.create(
        schedule_id=ScheduleId("active-history"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:active"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant().add(Duration.minutes(10)),
            ),
        ),
        reference=_instant(),
    )
    occurrence = Occurrence(
        schedule_id=schedule.id,
        schedule_revision=schedule.revision,
        scheduled_at=_instant().add(Duration.minutes(10)),
    )
    request = ExecutionRequest.from_occurrence(
        occurrence=occurrence,
        target=schedule.definition.target,
        created_at=_instant(),
    )
    request.mark_dispatched()
    execution = Execution.from_request(
        request=request,
        created_at=_instant(),
    )

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.executions.add(execution)
        uow.commit()

    clock.advance(Duration.days(365))
    scheduler = Scheduler(clock=clock, uow_factory=factory)
    result = scheduler.cleanup(
        RetentionPolicy.days(
            execution_history=30,
            published_outbox=30,
        ),
        limit=100,
    )

    assert result.execution_graphs_deleted == 0
    with factory() as uow:
        assert uow.executions.get(execution.id) is not None
        assert uow.requests.get(request.id) is not None


def test_t_retention_memory_002_limit_is_global_cleanup_budget() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)

    for index in range(3):
        scheduler.add_schedule(
            id=f"bounded-{index}",
            target=lambda: None,
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant().add(Duration.minutes(10)),
            ),
        )

    clock.advance(Duration.minutes(10))
    cycle = scheduler.run_pending(limit=10)
    assert len(cycle.executions) == 3
    clock.advance(Duration.days(31))

    first = scheduler.cleanup(
        RetentionPolicy.days(
            execution_history=30,
            published_outbox=30,
        ),
        limit=2,
    )
    second = scheduler.cleanup(
        RetentionPolicy.days(
            execution_history=30,
            published_outbox=30,
        ),
        limit=2,
    )

    assert first.total_deleted == 2
    assert second.total_deleted >= 1
