"""Persist a schedule in SQLite and continue after Scheduler restart."""

from pathlib import Path
from tempfile import TemporaryDirectory

from pyschedulekit import (
    Duration,
    ExecutionState,
    Instant,
    IntervalTrigger,
    Scheduler,
    SqliteUnitOfWorkFactory,
)
from pyschedulekit.testing import MutableClock


def main() -> None:
    clock = MutableClock(Instant.parse("2026-01-01T10:00:00Z"))
    calls: list[str] = []

    def refresh_catalog() -> None:
        calls.append(clock.now().value.isoformat())

    with TemporaryDirectory() as directory:
        database = Path(directory) / "scheduler.db"

        first_scheduler = Scheduler(
            clock=clock,
            uow_factory=SqliteUnitOfWorkFactory(database),
        )
        target = first_scheduler.register_target("refresh-catalog", refresh_catalog)
        first_scheduler.add_schedule(
            id="catalog-refresh",
            target=target,
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=Instant.parse("2026-01-01T10:10:00Z"),
            ),
        )

        clock.set(Instant.parse("2026-01-01T10:10:00Z"))
        first = first_scheduler.run_pending()
        assert first.executions[0].execution.state is ExecutionState.SUCCESS

        restarted = Scheduler(
            clock=clock,
            uow_factory=SqliteUnitOfWorkFactory(database),
        )
        restarted.register_target("refresh-catalog", refresh_catalog)

        snapshot = restarted.inspect_schedule("catalog-refresh")
        assert snapshot.next_run_time == Instant.parse("2026-01-01T10:20:00Z")

        clock.set(Instant.parse("2026-01-01T10:20:00Z"))
        second = restarted.run_pending()

        assert second.executions[0].execution.state is ExecutionState.SUCCESS
        assert len(calls) == 2

    print("sqlite: schedule resumed successfully after restart")


if __name__ == "__main__":
    main()
