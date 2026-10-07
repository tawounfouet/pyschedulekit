"""LOT-31 SQLite integration tests for operational control."""

from datetime import UTC, datetime

from pyschedulekit import (
    Duration,
    Instant,
    IntervalTrigger,
    ScheduleState,
    Scheduler,
    SqliteUnitOfWorkFactory,
)
from pyschedulekit.testing import MutableClock


def _instant(minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, minute, tzinfo=UTC))


def test_t_operations_sql_001_schedule_control_survives_scheduler_restart(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    clock = MutableClock(_instant())
    first = Scheduler(
        clock=clock,
        uow_factory=SqliteUnitOfWorkFactory(database),
    )
    schedule_id = first.add_schedule(
        id="durable-control",
        target=lambda: None,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(10),
        ),
    )

    paused = first.pause_schedule(schedule_id)
    assert paused.state is ScheduleState.PAUSED

    second = Scheduler(
        clock=clock,
        uow_factory=SqliteUnitOfWorkFactory(database),
    )
    inspected = second.inspect_schedule(schedule_id)

    assert inspected.state is ScheduleState.PAUSED
    assert inspected.next_run_time is None

    clock.set(_instant(25))
    resumed = second.resume_schedule(schedule_id)

    assert resumed.state is ScheduleState.ACTIVE
    assert resumed.next_run_time == _instant(30)

    third = Scheduler(
        clock=clock,
        uow_factory=SqliteUnitOfWorkFactory(database),
    )
    assert third.inspect_schedule(schedule_id).next_run_time == _instant(30)
