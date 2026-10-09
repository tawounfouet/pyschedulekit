"""Run one deterministic interval schedule without sleeping."""

from datetime import UTC, datetime

from pyschedulekit import Duration, Instant, IntervalTrigger, Scheduler
from pyschedulekit.testing import MutableClock


def main() -> tuple[int, list[str]]:
    clock = MutableClock(Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC)))
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="inventory-refresh",
        target=lambda: calls.append("refreshed"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=Instant(datetime(2026, 1, 1, 10, 10, tzinfo=UTC)),
        ),
    )

    before_due = scheduler.run_pending()
    assert before_due.succeeded == 0
    assert calls == []

    clock.advance(Duration.minutes(10))
    due = scheduler.run_pending()

    assert due.succeeded == 1
    assert calls == ["refreshed"]
    return due.succeeded, calls


if __name__ == "__main__":
    succeeded, calls = main()
    print(f"succeeded={succeeded} calls={calls}")
