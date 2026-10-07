"""LOT-24 end-to-end reconciliation qualification."""

from datetime import UTC, datetime

from pyschedulekit import Scheduler
from pyschedulekit.domain.execution import ExecutionState
from pyschedulekit.domain.execution_request import ExecutionRequest
from pyschedulekit.domain.occurrence import Occurrence
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleRevision,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def test_t_reconciliation_e2e_001_reconstructs_then_executes_missing_execution(
    tmp_path,
) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)

    schedule = Schedule.create(
        schedule_id=ScheduleId("reconcile-e2e"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:reconcile-e2e"),
            trigger=IntervalTrigger(
                every=Duration.hours(1),
                anchor=_instant(hour=11),
            ),
        ),
        reference=_instant(hour=9),
    )
    occurrence = Occurrence(
        schedule_id=schedule.id,
        schedule_revision=ScheduleRevision(1),
        scheduled_at=_instant(),
    )
    request = ExecutionRequest.from_occurrence(
        occurrence=occurrence,
        target=schedule.definition.target,
        created_at=_instant(),
    )
    request.mark_dispatched()

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.commit()

    calls: list[str] = []
    scheduler = Scheduler(
        clock=MutableClock(_instant(minute=1)),
        uow_factory=SqliteUnitOfWorkFactory(database),
    )
    scheduler.register_target(
        "jobs:reconcile-e2e",
        lambda: calls.append("ran"),
    )

    result = scheduler.run_pending()

    assert scheduler.last_reconciliation_result is not None
    assert scheduler.last_reconciliation_result.complete is True
    assert len(scheduler.last_reconciliation_result.reconstructed_execution_ids) == 1
    assert calls == ["ran"]
    assert len(result.executions) == 1
    assert result.executions[0].execution.state is ExecutionState.SUCCESS
