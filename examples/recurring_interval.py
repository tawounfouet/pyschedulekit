"""Run a fixed-rate recurring job twice."""

from pyschedulekit import Duration, ExecutionState, Instant, IntervalTrigger, Scheduler
from pyschedulekit.testing import MutableClock


def main() -> None:
    clock = MutableClock(Instant.parse("2026-01-01T10:00:00Z"))
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="catalog-refresh",
        target=lambda: calls.append(clock.now().value.isoformat()),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=Instant.parse("2026-01-01T10:10:00Z"),
        ),
    )

    clock.set(Instant.parse("2026-01-01T10:10:00Z"))
    first = scheduler.run_pending()

    clock.set(Instant.parse("2026-01-01T10:20:00Z"))
    second = scheduler.run_pending()

    assert len(calls) == 2
    assert first.executions[0].execution.state is ExecutionState.SUCCESS
    assert second.executions[0].execution.state is ExecutionState.SUCCESS
    print("interval: two anchored refreshes completed")


if __name__ == "__main__":
    main()
