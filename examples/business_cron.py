"""Run a weekday 09:00 Europe/Paris cron job."""

from pyschedulekit import CronTrigger, Duration, ExecutionState, Instant, Scheduler, Timezone
from pyschedulekit.testing import MutableClock


def main() -> None:
    clock = MutableClock(Instant.parse("2026-01-05T07:59:00Z"))
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="paris-opening",
        target=lambda: calls.append("opened"),
        trigger=CronTrigger(
            "0 9 * * 1-5",
            timezone=Timezone("Europe/Paris"),
        ),
    )

    clock.advance(Duration.minutes(1))
    result = scheduler.run_pending()

    assert calls == ["opened"]
    assert result.executions[0].execution.state is ExecutionState.SUCCESS
    print("cron: weekday 09:00 Europe/Paris job completed")


if __name__ == "__main__":
    main()
