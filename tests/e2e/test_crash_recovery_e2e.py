"""LOT-23 end-to-end crash recovery across a SQLite restart."""

from datetime import UTC, datetime

from pyschedulekit import Duration, FixedBackoff, RetryPolicy, Scheduler
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.domain.execution import AttemptState, ExecutionState
from pyschedulekit.domain.execution_request import ExecutionRequest
from pyschedulekit.domain.occurrence import Occurrence
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleRevision,
    TargetRef,
)
from pyschedulekit.domain.time import Instant
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def test_t_recovery_e2e_001_restart_recovers_then_retry_succeeds(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)
    retry = RetryPolicy(
        max_attempts=2,
        backoff=FixedBackoff(Duration.minutes(5)),
    )
    schedule = Schedule.create(
        schedule_id=ScheduleId("restart-recovery"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:restart-recovery"),
            trigger=IntervalTrigger(
                every=Duration.hours(1),
                anchor=_instant(hour=11),
            ),
            retry=retry,
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
        retry_policy=retry,
    )

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.commit()

    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(
        request_id=request.id,
        created_at=_instant(),
    )
    service.start_attempt(
        execution_id=execution.id,
        started_at=_instant(),
    )

    restarted_clock = MutableClock(_instant(minute=1))
    restarted = Scheduler(
        clock=restarted_clock,
        uow_factory=SqliteUnitOfWorkFactory(database),
    )
    calls: list[str] = []
    restarted.register_target(
        "jobs:restart-recovery",
        lambda: calls.append("attempt-2"),
    )

    first_cycle = restarted.run_pending()

    assert calls == []
    assert first_cycle.executions == ()
    assert restarted.last_recovery_result is not None
    assert restarted.last_recovery_result.retried_execution_ids == (execution.id,)

    restarted_clock.advance(Duration.minutes(5))
    second_cycle = restarted.run_pending()

    assert calls == ["attempt-2"]
    assert len(second_cycle.executions) == 1
    assert second_cycle.executions[0].execution.state is ExecutionState.SUCCESS

    with factory() as uow:
        recovered = uow.executions.get(execution.id)
        attempts = uow.attempts.list_for_execution(execution.id)

        assert recovered is not None
        assert recovered.state is ExecutionState.SUCCESS
        assert recovered.attempt_count == 2
        assert [attempt.state for attempt in attempts] == [
            AttemptState.FAILED,
            AttemptState.SUCCESS,
        ]
        assert attempts[0].result is not None
        assert attempts[0].result.failure is not None
        assert attempts[0].result.failure.code == "execution.crash_recovered"
