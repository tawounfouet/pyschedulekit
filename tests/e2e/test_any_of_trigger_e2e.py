"""CMP-05 public end-to-end qualification for AnyOfTrigger."""

from datetime import UTC, datetime
from pathlib import Path

from pyschedulekit import (
    AnyOfTrigger,
    Duration,
    Instant,
    IntervalTrigger,
    Scheduler,
    SqliteUnitOfWorkFactory,
)
from pyschedulekit.testing import MutableClock


def _instant() -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))


def _trigger(start: Instant) -> AnyOfTrigger:
    return AnyOfTrigger(
        IntervalTrigger(every=Duration.minutes(10), anchor=start.add(Duration.minutes(10))),
        IntervalTrigger(every=Duration.minutes(15), anchor=start.add(Duration.minutes(15))),
    )


def test_public_scheduler_runs_duplicate_free_union_in_chronological_order() -> None:
    start = _instant()
    clock = MutableClock(start)
    calls: list[str] = []
    scheduler = Scheduler(clock=clock)

    schedule_id = scheduler.add_schedule(
        id="composite-public",
        target=lambda: calls.append("ran"),
        trigger=_trigger(start),
    )

    expected_minutes = (10, 15, 20, 30)
    for minute in expected_minutes:
        clock.set(start.add(Duration.minutes(minute)))
        result = scheduler.run_pending()
        assert result.succeeded == 1

    assert len(calls) == len(expected_minutes)
    assert scheduler.inspect_schedule(schedule_id).next_run_time == start.add(Duration.minutes(40))


def test_public_any_of_schedule_survives_sqlite_reopen(tmp_path: Path) -> None:
    start = _instant()
    clock = MutableClock(start)
    database = tmp_path / "composite.db"
    scheduler = Scheduler(
        clock=clock,
        uow_factory=SqliteUnitOfWorkFactory(database),
    )

    schedule_id = scheduler.add_schedule(
        id="composite-durable",
        target=lambda: None,
        trigger=_trigger(start),
    )
    clock.set(start.add(Duration.minutes(10)))
    assert scheduler.run_pending().succeeded == 1

    reopened = Scheduler(
        clock=clock,
        uow_factory=SqliteUnitOfWorkFactory(database),
    )

    assert reopened.inspect_schedule(schedule_id).next_run_time == start.add(Duration.minutes(15))
