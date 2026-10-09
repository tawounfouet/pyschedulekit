"""Inspect schedule state plus Scheduler health/readiness."""

from datetime import UTC, datetime

from pyschedulekit import Duration, Instant, IntervalTrigger, Scheduler
from pyschedulekit.testing import MutableClock


def main() -> tuple[bool, bool, str]:
    clock = MutableClock(Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC)))
    scheduler = Scheduler(clock=clock, worker_id="ops-demo")

    scheduler.add_schedule(
        id="reporting",
        target=lambda: None,
        trigger=IntervalTrigger(
            every=Duration.hours(1),
            anchor=Instant(datetime(2026, 1, 1, 11, 0, tzinfo=UTC)),
        ),
    )

    # Readiness becomes true after the startup recovery/reconciliation barriers run.
    before = scheduler.readiness()
    assert not before.ready

    scheduler.run_pending()

    health = scheduler.health()
    ready = scheduler.readiness()
    schedule = scheduler.inspect_schedule("reporting")

    assert health.healthy
    assert health.worker_id == "ops-demo"
    assert ready.ready
    assert schedule.state.value == "active"

    paused = scheduler.pause_schedule("reporting")
    assert paused.state.value == "paused"

    resumed = scheduler.resume_schedule("reporting")
    assert resumed.state.value == "active"

    return health.healthy, ready.ready, resumed.state.value


if __name__ == "__main__":
    healthy, ready, state = main()
    print(f"healthy={healthy} ready={ready} schedule_state={state}")
