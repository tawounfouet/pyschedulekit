"""Installed-package dogfooding consumer for PyScheduleKit.

This script intentionally imports PyScheduleKit only through the stable root API.
It is executed from outside the repository source tree after wheel/sdist installation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

from pyschedulekit import (
    Duration,
    FixedBackoff,
    Instant,
    IntervalTrigger,
    RetryPolicy,
    Scheduler,
    SqliteUnitOfWorkFactory,
)


class ConsumerClock:
    """Tiny consumer-owned deterministic Clock implementation."""

    def __init__(self, current: Instant) -> None:
        self._current = current

    def now(self) -> Instant:
        return self._current

    def advance(self, duration: Duration) -> None:
        self._current = self._current.add(duration)


def run_consumer(database: Path) -> tuple[int, bool, bool, str]:
    start = Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    clock = ConsumerClock(start)
    attempts = 0

    first = Scheduler(
        clock=clock,
        uow_factory=SqliteUnitOfWorkFactory(database),
        worker_id="consumer-a",
    )

    def sync_job() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary dependency failure")

    target = first.register_target("consumer:sync", sync_job)
    first.add_schedule(
        id="consumer-sync",
        target=target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=start.add(Duration.minutes(10)),
        ),
        retry=RetryPolicy(
            max_attempts=3,
            backoff=FixedBackoff(Duration.minutes(2)),
        ),
    )

    clock.advance(Duration.minutes(10))
    first_cycle = first.run_pending()
    assert first_cycle.retry_scheduled == 1
    assert attempts == 1

    clock.advance(Duration.minutes(2))
    retry_cycle = first.run_pending()
    assert retry_cycle.succeeded == 1
    assert attempts == 2

    # Simulate a fresh consumer process opening the same durable state.
    reopened = Scheduler(
        clock=clock,
        uow_factory=SqliteUnitOfWorkFactory(database),
        worker_id="consumer-b",
    )
    reopened.register_target("consumer:sync", lambda: None)

    schedule = reopened.inspect_schedule("consumer-sync")
    persisted = schedule.next_run_time == start.add(Duration.minutes(20))
    assert persisted

    before = reopened.readiness()
    assert not before.ready

    # No schedule is due at 10:12, but startup recovery/reconciliation still run.
    idle_cycle = reopened.run_pending()
    assert idle_cycle.executions == ()

    after = reopened.readiness()
    health = reopened.health()
    assert after.ready
    assert health.healthy
    assert health.persistence_available

    paused = reopened.pause_schedule("consumer-sync")
    assert paused.state.value == "paused"
    resumed = reopened.resume_schedule("consumer-sync")
    assert resumed.state.value == "active"

    return attempts, persisted, after.ready, resumed.state.value


def main() -> None:
    with TemporaryDirectory() as directory:
        attempts, persisted, ready, state = run_consumer(
            Path(directory) / "consumer.db"
        )

    installed_version = version("pyschedulekit")
    print(
        "dogfood-ok "
        f"version={installed_version} "
        f"attempts={attempts} "
        f"persisted={persisted} "
        f"ready={ready} "
        f"state={state}"
    )


if __name__ == "__main__":
    main()
