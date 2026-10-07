"""LOT-31 end-to-end qualification for the public operational API."""

from datetime import UTC, datetime

from pyschedulekit import (
    Duration,
    ExecutionId,
    Instant,
    IntervalTrigger,
    ScheduleState,
    Scheduler,
)
from pyschedulekit.testing import MutableClock


def _instant(minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, minute, tzinfo=UTC))


def test_t_operational_e2e_001_schedule_control_and_inspection() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)

    schedule_id = scheduler.add_schedule(
        id="controlled",
        target=lambda: None,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(10),
        ),
    )

    initial = scheduler.inspect_schedule(schedule_id)
    assert initial.state is ScheduleState.ACTIVE
    assert initial.next_run_time == _instant(10)

    paused = scheduler.pause_schedule(schedule_id)
    assert paused.state is ScheduleState.PAUSED
    assert paused.next_run_time is None

    clock.set(_instant(25))
    resumed = scheduler.resume_schedule(schedule_id)
    assert resumed.state is ScheduleState.ACTIVE
    assert resumed.next_run_time == _instant(30)

    cancelled = scheduler.cancel_schedule(schedule_id)
    assert cancelled.state is ScheduleState.CANCELLED
    assert scheduler.inspect_schedule(schedule_id).state is ScheduleState.CANCELLED


def test_t_operational_e2e_002_execution_inspection_returns_snapshot() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)

    schedule_id = scheduler.add_schedule(
        id="execution-inspection",
        target=lambda: None,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(10),
        ),
    )

    clock.set(_instant(10))
    result = scheduler.run_pending()

    assert len(result.executions) == 1
    execution_id = result.executions[0].execution.id
    snapshot = scheduler.inspect_execution(execution_id)

    assert snapshot.execution_id == execution_id
    assert snapshot.state == "success"
    assert snapshot.attempt_count == 1
    assert snapshot.is_terminal is True
    assert snapshot.completed_at is not None
    assert schedule_id.value in scheduler.inspect_schedule(schedule_id).schedule_id.value


def test_t_operational_e2e_003_health_and_readiness_are_separate() -> None:
    scheduler = Scheduler(clock=MutableClock(_instant()))

    health_before = scheduler.health()
    readiness_before = scheduler.readiness()

    assert health_before.healthy is True
    assert health_before.persistence_available is True
    assert readiness_before.ready is False
    assert readiness_before.recovered is False
    assert readiness_before.reconciled is False

    scheduler.run_pending()

    readiness_after = scheduler.readiness()
    assert readiness_after.ready is True
    assert readiness_after.recovered is True
    assert readiness_after.reconciled is True


def test_t_operational_e2e_004_execution_id_accepts_public_string_form() -> None:
    scheduler = Scheduler(clock=MutableClock(_instant()))

    try:
        scheduler.inspect_execution(ExecutionId("missing"))
    except LookupError as exc:
        assert str(exc) == "missing"
