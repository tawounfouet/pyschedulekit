"""Persist scheduling state in SQLite and inspect it after reopening."""

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from pyschedulekit import Duration, Instant, IntervalTrigger, Scheduler, SqliteUnitOfWorkFactory
from pyschedulekit.testing import MutableClock


def main() -> None:
    start = Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))

    with TemporaryDirectory() as directory:
        database = Path(directory) / "scheduler.db"
        clock = MutableClock(start)
        scheduler = Scheduler(
            clock=clock,
            uow_factory=SqliteUnitOfWorkFactory(database),
        )
        calls: list[str] = []

        scheduler.add_schedule(
            id="durable-job",
            target=lambda: calls.append("ran"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=start.add(Duration.minutes(10)),
            ),
        )

        clock.advance(Duration.minutes(10))
        result = scheduler.run_pending()
        assert result.succeeded == 1
        assert calls == ["ran"]

        reopened = Scheduler(
            clock=clock,
            uow_factory=SqliteUnitOfWorkFactory(database),
        )
        snapshot = reopened.inspect_schedule("durable-job")

        assert snapshot.next_run_time == start.add(Duration.minutes(20))
        print("sqlite durability: schedule survived database reopen")


if __name__ == "__main__":
    main()
