"""Retry one transient failure after a deterministic fixed backoff."""

from datetime import UTC, datetime

from pyschedulekit import (
    Duration,
    FixedBackoff,
    Instant,
    IntervalTrigger,
    RetryPolicy,
    Scheduler,
)
from pyschedulekit.testing import MutableClock


def main() -> tuple[int, int]:
    clock = MutableClock(Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC)))
    scheduler = Scheduler(clock=clock)
    attempts = 0

    def flaky_job() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary upstream failure")

    scheduler.add_schedule(
        id="retry-demo",
        target=flaky_job,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=Instant(datetime(2026, 1, 1, 10, 10, tzinfo=UTC)),
        ),
        retry=RetryPolicy(
            max_attempts=3,
            backoff=FixedBackoff(Duration.minutes(5)),
        ),
    )

    clock.advance(Duration.minutes(10))
    first = scheduler.run_pending()
    assert first.retry_scheduled == 1
    assert attempts == 1

    # The retry is not eligible until the backoff expires.
    assert scheduler.run_pending().executions == ()

    clock.advance(Duration.minutes(5))
    second = scheduler.run_pending()
    assert second.succeeded == 1
    assert attempts == 2

    return attempts, second.succeeded


if __name__ == "__main__":
    attempts, succeeded = main()
    print(f"attempts={attempts} succeeded={succeeded}")
