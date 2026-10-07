"""LOT-26 end-to-end multi-worker claim qualification."""

from datetime import UTC, datetime

from pyschedulekit import Duration, IntervalTrigger, Scheduler, SqliteUnitOfWorkFactory
from pyschedulekit.testing import MutableClock


def _instant():
    from pyschedulekit import Instant

    return Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))


def test_t_claim_e2e_001_second_scheduler_cannot_execute_claimed_work(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)
    clock = MutableClock(_instant())
    first = Scheduler(
        clock=clock,
        uow_factory=factory,
        worker_id="worker-a",
        claim_ttl=Duration.seconds(30),
    )
    second = Scheduler(
        clock=clock,
        uow_factory=SqliteUnitOfWorkFactory(database),
        worker_id="worker-b",
        claim_ttl=Duration.seconds(30),
    )
    calls: list[str] = []

    first.add_schedule(
        id="claims-e2e",
        target=lambda: calls.append("worker-a"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant().add(Duration.minutes(10)),
        ),
    )
    second.register_target("local:claims-e2e", lambda: calls.append("worker-b"))

    clock.advance(Duration.minutes(10))

    first_result = first.run_pending()
    second_result = second.run_pending()

    assert first_result.succeeded == 1
    assert second_result.succeeded == 0
    assert calls == ["worker-a"]
