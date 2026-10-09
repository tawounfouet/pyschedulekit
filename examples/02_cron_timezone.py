"""Run a weekday Paris cron schedule deterministically."""

from datetime import UTC, datetime

from pyschedulekit import CronTrigger, Duration, Instant, Scheduler, Timezone
from pyschedulekit.testing import MutableClock


def main() -> None:
    # 08:00 UTC is 09:00 in Paris on 2026-01-05.
    start = Instant(datetime(2026, 1, 5, 7, 59, tzinfo=UTC))
    clock = MutableClock(start)
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="paris-business-open",
        target=lambda: calls.append("open"),
        trigger=CronTrigger(
            "0 9 * * 1-5",
            timezone=Timezone("Europe/Paris"),
        ),
    )

    assert scheduler.run_pending().succeeded == 0
    clock.advance(Duration.minutes(1))
    result = scheduler.run_pending()

    assert result.succeeded == 1
    assert calls == ["open"]
    print("cron timezone: Paris weekday 09:00 executed")


if __name__ == "__main__":
    main()
