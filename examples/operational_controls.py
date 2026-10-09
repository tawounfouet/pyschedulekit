"""Pause, resume, inspect, execute, and cancel one schedule."""

from pyschedulekit import (
    Duration,
    ExecutionState,
    Instant,
    IntervalTrigger,
    ScheduleState,
    Scheduler,
)
from pyschedulekit.testing import MutableClock


def main() -> None:
    clock = MutableClock(Instant.parse("2026-01-01T10:00:00Z"))
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    schedule_id = scheduler.add_schedule(
        id="billing-export",
        target=lambda: calls.append("exported"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=Instant.parse("2026-01-01T10:10:00Z"),
        ),
    )

    assert scheduler.inspect_schedule(schedule_id).state is ScheduleState.ACTIVE
    assert scheduler.pause_schedule(schedule_id).state is ScheduleState.PAUSED

    clock.set(Instant.parse("2026-01-01T10:25:00Z"))
    assert scheduler.run_pending().executions == ()

    resumed = scheduler.resume_schedule(schedule_id)
    assert resumed.state is ScheduleState.ACTIVE
    assert resumed.next_run_time == Instant.parse("2026-01-01T10:30:00Z")

    clock.set(Instant.parse("2026-01-01T10:30:00Z"))
    result = scheduler.run_pending()
    assert calls == ["exported"]
    assert result.executions[0].execution.state is ExecutionState.SUCCESS

    assert scheduler.cancel_schedule(schedule_id).state is ScheduleState.CANCELLED
    print("operations: pause/resume/run/cancel lifecycle completed")


if __name__ == "__main__":
    main()
