"""LOT-29 end-to-end qualification for ongoing distributed recovery."""

from datetime import UTC, datetime

from pyschedulekit import Duration, IntervalTrigger, RetryPolicy, Scheduler
from pyschedulekit.application.claims import ExecutionClaimCoordinator
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.domain.claim import ExecutionClaimState, WorkerId
from pyschedulekit.domain.execution import AttemptState, ExecutionState
from pyschedulekit.domain.execution_request import ExecutionRequest
from pyschedulekit.domain.occurrence import Occurrence
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleRevision,
    TargetRef,
)
from pyschedulekit.domain.time import Instant
from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory
from pyschedulekit.testing import MutableClock


def _instant(second: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, second, tzinfo=UTC))


def test_t_coord_e2e_001_running_scheduler_recovers_expired_foreign_lease(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)
    schedule = Schedule.create(
        schedule_id=ScheduleId("orphan"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:orphan"),
            trigger=IntervalTrigger(
                every=Duration.hours(1),
                anchor=Instant(datetime(2026, 1, 1, 11, 0, tzinfo=UTC)),
            ),
            retry=RetryPolicy.none(),
        ),
        reference=Instant(datetime(2026, 1, 1, 9, 0, tzinfo=UTC)),
    )
    occurrence = Occurrence(
        schedule_id=schedule.id,
        schedule_revision=ScheduleRevision(1),
        scheduled_at=_instant(),
    )
    request = ExecutionRequest.from_occurrence(
        occurrence=occurrence,
        target=schedule.definition.target,
        created_at=_instant(),
        retry_policy=RetryPolicy.none(),
    )
    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.commit()

    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(
        request_id=request.id,
        created_at=_instant(),
    )
    owner = ExecutionClaimCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-a"),
        ttl=Duration.seconds(30),
    )
    acquired = owner.acquire(execution_id=execution.id, now=_instant())
    assert acquired.handle is not None
    attempt = service.start_attempt(
        execution_id=execution.id,
        started_at=_instant(),
        claim_handle=acquired.handle,
    )

    clock = MutableClock(_instant(10))
    scheduler = Scheduler(
        clock=clock,
        uow_factory=SqliteUnitOfWorkFactory(database),
        worker_id="worker-b",
        claim_ttl=Duration.seconds(30),
    )

    first = scheduler.run_pending()

    assert first.executions == ()
    with factory() as uow:
        protected = uow.executions.get(execution.id)
        assert protected is not None
        assert protected.state is ExecutionState.RUNNING

    clock.set(_instant(30))
    second = scheduler.run_pending()

    assert second.executions == ()
    with factory() as uow:
        recovered = uow.executions.get(execution.id)
        recovered_attempt = uow.attempts.get(attempt.id)
        claim = uow.claims.get(execution.id)
        assert recovered is not None
        assert recovered_attempt is not None
        assert claim is not None
        assert recovered.state is ExecutionState.FAILED
        assert recovered_attempt.state is AttemptState.FAILED
        assert claim.state is ExecutionClaimState.RELEASED
        assert claim.worker_id == WorkerId("worker-b")
        assert claim.generation == acquired.handle.generation + 1
