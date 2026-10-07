"""LOT-15 end-to-end retry qualification through the public Scheduler."""

from datetime import UTC, datetime

from pyschedulekit import (
    Duration,
    FixedBackoff,
    IntervalTrigger,
    RetryPolicy,
    Scheduler,
)
from pyschedulekit.domain.execution import ExecutionState
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0):
    from pyschedulekit import Instant

    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def test_t_retry_e2e_001_fail_then_success_after_fixed_backoff() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls = 0

    def target() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary")

    scheduler.add_schedule(
        id="retry-fixed",
        target=target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
        retry=RetryPolicy(
            max_attempts=3,
            backoff=FixedBackoff(Duration.minutes(5)),
        ),
    )

    clock.advance(Duration.minutes(10))
    first = scheduler.run_pending()

    assert calls == 1
    assert len(first.executions) == 1
    assert first.executions[0].execution.state is ExecutionState.RETRY_WAIT
    assert first.retry_scheduled == 1
    assert first.failed == 0

    before_deadline = scheduler.run_pending()
    assert before_deadline.executions == ()
    assert calls == 1

    clock.advance(Duration.minutes(5))
    second = scheduler.run_pending()

    assert calls == 2
    assert len(second.executions) == 1
    assert second.executions[0].execution.state is ExecutionState.SUCCESS
    assert second.executions[0].execution.attempt_count == 2
    assert second.succeeded == 1


def test_t_retry_e2e_002_attempt_exhaustion_fails_execution() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls = 0

    def target() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("always fails")

    scheduler.add_schedule(
        id="retry-exhausted",
        target=target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
        retry=RetryPolicy(max_attempts=2),
    )

    clock.advance(Duration.minutes(10))
    first = scheduler.run_pending()
    second = scheduler.run_pending()

    assert first.retry_scheduled == 1
    assert first.failed == 0
    assert second.retry_scheduled == 0
    assert second.failed == 1
    assert second.executions[0].execution.state is ExecutionState.FAILED
    assert second.executions[0].execution.attempt_count == 2
    assert calls == 2
