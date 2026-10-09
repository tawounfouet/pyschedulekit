"""Deterministic interval-scheduling quickstart."""

from datetime import UTC, datetime

from pyschedulekit import Duration, Instant, IntervalTrigger, Scheduler
from pyschedulekit.testing import MutableClock


def main() -> None:
    start = Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    clock = MutableClock(start)
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="heartbeat",
        target=lambda: calls.append("heartbeat"),
        trigger=IntervalTrigger(
            every=Duration.minutes(5),
            anchor=start.add(Duration.minutes(5)),
        ),
    )

    before_due = scheduler.run_pending()
    assert before_due.succeeded == 0
    assert calls == []

    clock.advance(Duration.minutes(5))
    due = scheduler.run_pending()

    assert due.succeeded == 1
    assert calls == ["heartbeat"]
    print("interval quickstart: heartbeat executed once")


if __name__ == "__main__":
    main()
