"""Run one deterministic one-shot reporting job."""

from pyschedulekit import DateTrigger, ExecutionState, Instant, Scheduler
from pyschedulekit.testing import MutableClock


def main() -> None:
    clock = MutableClock(Instant.parse("2026-01-01T10:00:00Z"))
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="daily-report",
        target=lambda: calls.append("report-generated"),
        trigger=DateTrigger(Instant.parse("2026-01-01T10:05:00Z")),
    )

    assert scheduler.run_pending().executions == ()

    clock.set(Instant.parse("2026-01-01T10:05:00Z"))
    result = scheduler.run_pending()

    assert calls == ["report-generated"]
    assert result.succeeded == 1
    assert result.executions[0].execution.state is ExecutionState.SUCCESS
    print("one-shot: report generated successfully")


if __name__ == "__main__":
    main()
