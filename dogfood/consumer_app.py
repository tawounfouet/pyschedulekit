"""Consumer-style dogfood application executed against installed distributions."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pyschedulekit
from pyschedulekit import (
    CronTrigger,
    Duration,
    FixedBackoff,
    Instant,
    IntervalTrigger,
    RetryPolicy,
    Scheduler,
    SqliteUnitOfWorkFactory,
    Timezone,
)


class ManualClock:
    """Small consumer-owned clock used to make the dogfood scenario deterministic."""

    def __init__(self, current: Instant) -> None:
        self._current = current

    def now(self) -> Instant:
        return self._current

    def advance(self, duration: Duration) -> None:
        self._current = self._current.add(duration)


def _assert_installed_distribution() -> None:
    if os.environ.get("PYSCHEDULEKIT_DOGFOOD_REQUIRE_INSTALLED") != "1":
        return

    workspace = os.environ.get("GITHUB_WORKSPACE")
    if workspace is None:
        raise AssertionError("GITHUB_WORKSPACE is required for installed-package dogfooding.")

    package_path = Path(pyschedulekit.__file__).resolve()
    repository = Path(workspace).resolve()

    try:
        package_path.relative_to(repository)
    except ValueError:
        return

    raise AssertionError(
        f"Dogfood imported PyScheduleKit from the source checkout: {package_path}"
    )


def main() -> None:
    _assert_installed_distribution()

    start = Instant(datetime(2026, 1, 5, 7, 59, tzinfo=UTC))
    clock = ManualClock(start)
    events: list[str] = []
    sync_attempts = 0

    with TemporaryDirectory() as directory:
        database = Path(directory) / "consumer.db"
        scheduler = Scheduler(
            clock=clock,
            uow_factory=SqliteUnitOfWorkFactory(database),
            worker_id="dogfood-consumer",
        )

        def business_open() -> None:
            events.append("paris-open")

        def sync_records() -> None:
            nonlocal sync_attempts
            sync_attempts += 1
            if sync_attempts == 1:
                raise RuntimeError("simulated transient dependency failure")
            events.append("sync-complete")

        scheduler.add_schedule(
            id="business-open",
            target=business_open,
            trigger=CronTrigger(
                "0 9 * * 1-5",
                timezone=Timezone("Europe/Paris"),
            ),
        )
        scheduler.add_schedule(
            id="sync-records",
            target=sync_records,
            trigger=IntervalTrigger(
                every=Duration.minutes(15),
                anchor=start.add(Duration.minutes(1)),
            ),
            retry=RetryPolicy(
                max_attempts=3,
                backoff=FixedBackoff(Duration.minutes(2)),
            ),
        )

        before = scheduler.readiness()
        assert not before.ready

        clock.advance(Duration.minutes(1))
        first = scheduler.run_pending()

        assert first.succeeded == 1
        assert first.retry_scheduled == 1
        assert events == ["paris-open"]
        assert sync_attempts == 1
        assert scheduler.readiness().ready

        clock.advance(Duration.minutes(2))
        second = scheduler.run_pending()

        assert second.succeeded == 1
        assert second.retry_scheduled == 0
        assert events == ["paris-open", "sync-complete"]
        assert sync_attempts == 2

        sync_snapshot = scheduler.inspect_schedule("sync-records")
        assert sync_snapshot.next_run_time == start.add(Duration.minutes(16))

        health = scheduler.health()
        assert health.healthy
        assert health.persistence_available

        reopened = Scheduler(
            clock=clock,
            uow_factory=SqliteUnitOfWorkFactory(database),
            worker_id="dogfood-reopened",
        )
        assert reopened.inspect_schedule("business-open").schedule_id.value == "business-open"
        assert reopened.inspect_schedule("sync-records").schedule_id.value == "sync-records"

    print(
        "installed dogfood: cron + retry + SQLite + readiness completed "
        f"with PyScheduleKit {pyschedulekit.__version__}"
    )


if __name__ == "__main__":
    main()
