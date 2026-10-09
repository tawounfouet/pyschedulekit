"""Persist schedules in SQLite and reopen them in a new Scheduler."""

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from pyschedulekit import (
    Duration,
    Instant,
    IntervalTrigger,
    Scheduler,
    SqliteUnitOfWorkFactory,
)
from pyschedulekit.testing import MutableClock


def run_example(database: Path) -> tuple[str, str]:
    clock = MutableClock(Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC)))

    first = Scheduler(
        clock=clock,
        uow_factory=SqliteUnitOfWorkFactory(database),
        worker_id="worker-a",
    )
    calls: list[str] = []
    target = first.register_target("jobs:daily-sync", lambda: calls.append("worker-a"))

    first.add_schedule(
        id="durable-sync",
        target=target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=Instant(datetime(2026, 1, 1, 10, 10, tzinfo=UTC)),
        ),
    )

    clock.advance(Duration.minutes(10))
    assert first.run_pending().succeeded == 1

    # Python callables are process-local. A restarted process registers trusted code again,
    # while the Schedule itself is restored from SQLite.
    reopened = Scheduler(
        clock=clock,
        uow_factory=SqliteUnitOfWorkFactory(database),
        worker_id="worker-b",
    )
    reopened.register_target("jobs:daily-sync", lambda: calls.append("worker-b"))

    snapshot = reopened.inspect_schedule("durable-sync")
    assert snapshot.schedule_id.value == "durable-sync"
    assert snapshot.target_reference == "jobs:daily-sync"
    assert snapshot.next_run_time == Instant(datetime(2026, 1, 1, 10, 20, tzinfo=UTC))

    return snapshot.schedule_id.value, snapshot.target_reference


def main() -> tuple[str, str]:
    with TemporaryDirectory() as directory:
        return run_example(Path(directory) / "scheduler.db")


if __name__ == "__main__":
    schedule_id, target = main()
    print(f"schedule={schedule_id} target={target}")
