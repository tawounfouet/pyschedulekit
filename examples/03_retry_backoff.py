"""Retry a transient failure with deterministic fixed backoff."""

from datetime import UTC, datetime

from pyschedulekit import Duration, FixedBackoff, Instant, IntervalTrigger, RetryPolicy, Scheduler
from pyschedulekit.testing import MutableClock


def main() -> None:
    start = Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    clock = MutableClock(start)
    scheduler = Scheduler(clock=clock)
    attempts = 0

    def flaky_job() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary dependency failure")

    scheduler.add_schedule(
        id="retry-demo",
        target=flaky_job,
        trigger=IntervalTrigger(
            every=Duration.hours(1),
            anchor=start.add(Duration.minutes(1)),
        ),
        retry=RetryPolicy(
            max_attempts=3,
            backoff=FixedBackoff(Duration.minutes(5)),
        ),
    )

    clock.advance(Duration.minutes(1))
    first = scheduler.run_pending()
    assert first.retry_scheduled == 1
    assert attempts == 1

    # Nothing runs before the retry deadline.
    assert scheduler.run_pending().executions == ()

    clock.advance(Duration.minutes(5))
    second = scheduler.run_pending()

    assert second.succeeded == 1
    assert attempts == 2
    print("retry backoff: transient failure recovered on attempt 2")


if __name__ == "__main__":
    main()
