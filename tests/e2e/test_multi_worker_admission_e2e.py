"""LOT-27 end-to-end Scheduler admission-lock qualification."""

from datetime import UTC, datetime

from pyschedulekit import (
    ConcurrencyPolicy,
    Duration,
    IntervalTrigger,
    Scheduler,
    SqliteUnitOfWorkFactory,
)
from pyschedulekit.application.admission_lock import ScheduleAdmissionLockCoordinator
from pyschedulekit.domain.claim import WorkerId
from pyschedulekit.domain.execution_request import ExecutionRequest, ExecutionRequestState
from pyschedulekit.domain.occurrence import Occurrence
from pyschedulekit.domain.schedule import ScheduleId, ScheduleRevision
from pyschedulekit.domain.time import Instant
from pyschedulekit.testing import MutableClock


def _instant() -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))


def test_t_admission_e2e_001_scheduler_reports_durable_lock_contention(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)
    clock = MutableClock(_instant())

    owner = Scheduler(
        clock=clock,
        uow_factory=factory,
        worker_id="worker-a",
    )
    owner.add_schedule(
        id="shared",
        target=lambda: None,
        trigger=IntervalTrigger(
            every=Duration.hours(1),
            anchor=_instant().add(Duration.hours(1)),
        ),
        concurrency=ConcurrencyPolicy.limit(max_instances=1),
    )

    with factory() as uow:
        schedule = uow.schedules.get(ScheduleId("shared"))
        assert schedule is not None
        occurrence = Occurrence(
            schedule_id=schedule.id,
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        )
        request = ExecutionRequest.from_occurrence(
            occurrence=occurrence,
            target=schedule.definition.target,
            created_at=_instant(),
            concurrency_policy=schedule.definition.concurrency,
        )
        uow.requests.add(request)
        uow.commit()

    holder = ScheduleAdmissionLockCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-a"),
        ttl=Duration.seconds(5),
    )
    held = holder.acquire(schedule_id=ScheduleId("shared"), now=_instant())
    assert held.acquired

    contender = Scheduler(
        clock=clock,
        uow_factory=SqliteUnitOfWorkFactory(database),
        worker_id="worker-b",
    )
    result = contender.run_pending()

    assert result.admission_lock_denied_request_ids == (request.id,)
    assert result.queued_request_ids == ()
    assert result.executions == ()

    with factory() as uow:
        persisted = uow.requests.get(request.id)
        assert persisted is not None
        assert persisted.state is ExecutionRequestState.PENDING
        assert uow.executions.get_by_request(request.id) is None
