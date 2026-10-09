"""Schedule a weekday task at 09:00 Europe/Paris."""

from datetime import UTC, datetime

from pyschedulekit import CronTrigger, Duration, Instant, Scheduler, Timezone
from pyschedulekit.testing import MutableClock


def main() -> tuple[int, list[str]]:
    # 2026-01-05 is a Monday. 07:59 UTC == 08:59 Europe/Paris.
    clock = MutableClock(Instant(datetime(2026, 1, 5, 7, 59, tzinfo=UTC)))
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="weekday-opening",
        target=lambda: calls.append("opened"),
        trigger=CronTrigger(
            "0 9 * * 1-5",
            timezone=Timezone("Europe/Paris"),
        ),
    )

    assert scheduler.run_pending().succeeded == 0

    clock.advance(Duration.minutes(1))
    due = scheduler.run_pending()

    assert due.succeeded == 1
    assert calls == ["opened"]
    return due.succeeded, calls


if __name__ == "__main__":
    succeeded, calls = main()
    print(f"succeeded={succeeded} calls={calls}")
