"""Retry one timed-out job after a fixed backoff."""

from pyschedulekit import (
    Duration,
    ExecutionState,
    FixedBackoff,
    Instant,
    IntervalTrigger,
    RetryPolicy,
    Scheduler,
)
from pyschedulekit.testing import MutableClock


def main() -> None:
    clock = MutableClock(Instant.parse("2026-01-01T10:00:00Z"))
    scheduler = Scheduler(clock=clock)
    calls = 0

    def flaky_target() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            clock.advance(Duration.seconds(3))

    scheduler.add_schedule(
        id="partner-sync",
        target=flaky_target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=Instant.parse("2026-01-01T10:10:00Z"),
        ),
        timeout=Duration.seconds(2),
        retry=RetryPolicy(
            max_attempts=2,
            backoff=FixedBackoff(Duration.minutes(5)),
        ),
    )

    clock.set(Instant.parse("2026-01-01T10:10:00Z"))
    first = scheduler.run_pending()

    assert first.retry_scheduled == 1
    assert first.executions[0].execution.state is ExecutionState.RETRY_WAIT

    clock.advance(Duration.minutes(5))
    second = scheduler.run_pending()

    assert calls == 2
    assert second.succeeded == 1
    assert second.executions[0].execution.state is ExecutionState.SUCCESS
    assert second.executions[0].execution.attempt_count == 2
    print("retry: timeout recovered on attempt 2")


if __name__ == "__main__":
    main()
