"""LOT-16 end-to-end timeout qualification through the public Scheduler."""

from datetime import UTC, datetime

from pyschedulekit import (
    Duration,
    IntervalTrigger,
    RetryPolicy,
    Scheduler,
)
from pyschedulekit.domain.execution import ExecutionState
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0):
    from pyschedulekit import Instant

    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def test_t_timeout_e2e_001_public_timeout_marks_execution_timed_out() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)

    def target() -> None:
        clock.advance(Duration.seconds(3))

    scheduler.add_schedule(
        id="timeout-public",
        target=target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
        timeout=Duration.seconds(2),
    )

    clock.advance(Duration.minutes(10))
    result = scheduler.run_pending()

    assert len(result.executions) == 1
    assert result.executions[0].execution.state is ExecutionState.TIMED_OUT
    assert result.executions[0].outcome.failure is not None
    assert result.failed == 1


def test_t_timeout_e2e_002_timeout_retries_on_later_cycle() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls = 0

    def target() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            clock.advance(Duration.seconds(3))

    scheduler.add_schedule(
        id="timeout-retry",
        target=target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
        timeout=Duration.seconds(2),
        retry=RetryPolicy(max_attempts=2),
    )

    clock.advance(Duration.minutes(10))
    first = scheduler.run_pending()
    second = scheduler.run_pending()

    assert first.executions[0].execution.state is ExecutionState.RETRY_WAIT
    assert first.retry_scheduled == 1
    assert second.executions[0].execution.state is ExecutionState.SUCCESS
    assert second.executions[0].execution.attempt_count == 2
    assert calls == 2


def test_t_timeout_e2e_003_timeout_snapshot_survives_schedule_progression() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)

    def target() -> None:
        clock.advance(Duration.seconds(2))

    scheduler.add_schedule(
        id="timeout-snapshot",
        target=target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
        timeout=Duration.seconds(1),
    )

    clock.advance(Duration.minutes(10))
    result = scheduler.run_pending()

    assert result.executions[0].execution.policy_snapshot.timeout == Duration.seconds(1)
    assert result.executions[0].execution.state is ExecutionState.TIMED_OUT
