"""Combine two temporal rules into one duplicate-free schedule."""

from datetime import UTC, datetime

from pyschedulekit import AnyOfTrigger, Duration, Instant, IntervalTrigger, Scheduler
from pyschedulekit.testing import MutableClock


def main() -> None:
    start = Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    clock = MutableClock(start)
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="either-cadence",
        target=lambda: calls.append("ran"),
        trigger=AnyOfTrigger(
            IntervalTrigger(
                every=Duration.minutes(10),
                anchor=start.add(Duration.minutes(10)),
            ),
            IntervalTrigger(
                every=Duration.minutes(15),
                anchor=start.add(Duration.minutes(15)),
            ),
        ),
    )

    for minute in (10, 15, 20, 30):
        clock.set(start.add(Duration.minutes(minute)))
        assert scheduler.run_pending().succeeded == 1

    assert len(calls) == 4
    print("composite any-of: shared occurrence executed once")


if __name__ == "__main__":
    main()
