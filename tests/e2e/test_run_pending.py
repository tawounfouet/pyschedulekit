"""LOT-11 end-to-end tests for the public Scheduler facade."""

from datetime import UTC, datetime

from pyschedulekit import Duration, IntervalTrigger, Scheduler, TargetRef
from pyschedulekit.domain.execution import ExecutionState
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0):
    from pyschedulekit import Instant

    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def test_t_e2e_001_direct_callable_runs_once_when_due() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="schedule-1",
        target=lambda: calls.append("called"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )

    before_due = scheduler.run_pending()

    assert calls == []
    assert before_due.materialized_request_ids == ()
    assert before_due.executions == ()

    clock.advance(Duration.minutes(10))
    due = scheduler.run_pending()

    assert calls == ["called"]
    assert len(due.materialized_request_ids) == 1
    assert len(due.executions) == 1
    assert due.executions[0].execution.state is ExecutionState.SUCCESS
    assert due.succeeded == 1
    assert due.failed == 0
    assert due.errors == ()


def test_t_e2e_002_registered_target_ref_runs_successfully() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    target = scheduler.register_target(
        "refresh",
        lambda: calls.append("refresh"),
    )
    scheduler.add_schedule(
        id="schedule-1",
        target=target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )
    clock.advance(Duration.minutes(10))

    result = scheduler.run_pending()

    assert calls == ["refresh"]
    assert result.succeeded == 1
    assert result.failed == 0


def test_t_e2e_003_run_pending_captures_evaluation_now_once() -> None:
    class CountingClock:
        def __init__(self) -> None:
            self.calls = 0

        def now(self):
            self.calls += 1
            return _instant(hour=10, minute=self.calls - 1)

    clock = CountingClock()
    scheduler = Scheduler(clock=clock)
    scheduler.add_schedule(
        id="schedule-1",
        target=lambda: None,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )
    calls_before_run = clock.calls

    result = scheduler.run_pending()

    assert result.evaluation_now == _instant(hour=10, minute=calls_before_run)
    assert clock.calls >= calls_before_run + 1


def test_t_e2e_004_one_overdue_occurrence_per_schedule_per_cycle() -> None:
    clock = MutableClock(_instant(hour=10))
    scheduler = Scheduler(clock=clock)
    calls: list[int] = []

    scheduler.add_schedule(
        id="schedule-1",
        target=lambda: calls.append(len(calls) + 1),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )

    clock.advance(Duration.minutes(35))

    first = scheduler.run_pending()
    second = scheduler.run_pending()

    assert calls == [1, 2]
    assert len(first.executions) == 1
    assert len(second.executions) == 1


def test_t_e2e_005_callable_exception_is_reported_as_failed_execution() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)

    def failing() -> None:
        raise RuntimeError("boom")

    scheduler.add_schedule(
        id="schedule-1",
        target=failing,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )
    clock.advance(Duration.minutes(10))

    result = scheduler.run_pending()

    assert len(result.executions) == 1
    assert result.executions[0].execution.state is ExecutionState.FAILED
    assert result.succeeded == 0
    assert result.failed == 1
    assert result.errors == ()


def test_t_e2e_006_unresolved_target_isolated_from_other_request() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="a-missing",
        target=TargetRef.python("not-registered"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )
    scheduler.add_schedule(
        id="b-working",
        target=lambda: calls.append("working"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )

    clock.advance(Duration.minutes(10))
    result = scheduler.run_pending()

    assert calls == ["working"]
    assert len(result.materialized_request_ids) == 2
    assert len(result.executions) == 1
    assert result.executions[0].execution.state is ExecutionState.SUCCESS
    assert len(result.errors) == 1
    assert result.errors[0].code == "executor.target_resolution"


def test_t_e2e_007_limit_bounds_schedule_materialization() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    for schedule_id in ("schedule-c", "schedule-a", "schedule-b"):
        scheduler.add_schedule(
            id=schedule_id,
            target=lambda schedule_id=schedule_id: calls.append(schedule_id),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(hour=10, minute=10),
            ),
        )

    clock.advance(Duration.minutes(10))
    result = scheduler.run_pending(limit=2)

    assert len(result.materialized_request_ids) == 2
    assert calls == ["schedule-a", "schedule-b"]


def test_t_e2e_008_no_due_work_is_a_noop() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)

    result = scheduler.run_pending()

    assert result.materialized_request_ids == ()
    assert result.executions == ()
    assert result.skipped_execution_ids == ()
    assert result.schedule_conflicts == ()
    assert result.errors == ()
    assert result.succeeded == 0
    assert result.failed == 0
