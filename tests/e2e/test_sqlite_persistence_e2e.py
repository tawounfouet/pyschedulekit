"""LOT-21 end-to-end scheduler qualification on SQLite."""

from datetime import UTC, datetime

from pyschedulekit import Duration, IntervalTrigger, Scheduler
from pyschedulekit.domain.execution import ExecutionState
from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0):
    from pyschedulekit import Instant

    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def test_t_sql_e2e_001_scheduler_runs_on_sqlite_and_survives_reopen(tmp_path) -> None:
    database = tmp_path / "runtime.db"
    factory = SqliteUnitOfWorkFactory(database)
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock, uow_factory=factory)
    calls: list[str] = []

    scheduler.add_schedule(
        id="sqlite-runtime",
        target=lambda: calls.append("ran"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )

    clock.advance(Duration.minutes(10))
    result = scheduler.run_pending()

    assert calls == ["ran"]
    assert len(result.executions) == 1
    assert result.executions[0].execution.state is ExecutionState.SUCCESS

    reopened = SqliteUnitOfWorkFactory(database)
    with reopened() as uow:
        schedule = uow.schedules.get(result.executions[0].execution.request_id and __import__(
            "pyschedulekit.domain.schedule",
            fromlist=["ScheduleId"],
        ).ScheduleId("sqlite-runtime"))
        assert schedule is not None
        assert schedule.next_run_time == _instant(hour=10, minute=20)
