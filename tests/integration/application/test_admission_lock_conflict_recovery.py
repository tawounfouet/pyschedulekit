"""POST-00D regression tests for admission-lock conflict recovery."""

from datetime import UTC, datetime

from pyschedulekit.application.admission_lock import ScheduleAdmissionLockCoordinator
from pyschedulekit.application.concurrency import AdmissionResult, ConcurrencyCoordinator
from pyschedulekit.domain.admission_lock import (
    ScheduleAdmissionLockHandle,
    ScheduleAdmissionLockState,
)
from pyschedulekit.domain.claim import WorkerId
from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleRevision,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.ports.persistence import PersistenceConflictError


def _instant() -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))


class ConflictAfterLockCoordinator(ConcurrencyCoordinator):
    """Force the transaction conflict after durable lock acquisition."""

    def _admit_locked(
        self,
        *,
        request_id: RequestId,
        created_at: Instant,
        lock_handle: ScheduleAdmissionLockHandle | None,
    ) -> AdmissionResult:
        del request_id, created_at, lock_handle
        raise PersistenceConflictError("synthetic admission conflict")


def test_persistence_conflict_releases_owned_admission_lock_immediately() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule_id = ScheduleId("schedule-conflict")
    schedule = Schedule.create(
        schedule_id=schedule_id,
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:conflict"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(),
            ),
        ),
        reference=_instant(),
    )
    request = ExecutionRequest(
        id=RequestId("request-conflict"),
        occurrence_key=OccurrenceKey(
            schedule_id=schedule_id,
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        ),
        target=TargetRef.python("jobs:conflict"),
        created_at=_instant(),
    )
    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.commit()

    owner = ScheduleAdmissionLockCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-a"),
        ttl=Duration.seconds(5),
    )
    coordinator = ConflictAfterLockCoordinator(
        uow_factory=factory,
        admission_lock_coordinator=owner,
    )

    result = coordinator.admit(
        request_id=request.id,
        created_at=_instant(),
    )

    assert result.lock_denied is True
    assert result.execution is None

    with factory() as uow:
        persisted_lock = uow.admission_locks.get(schedule_id)

    assert persisted_lock is not None
    assert persisted_lock.state is ScheduleAdmissionLockState.RELEASED

    contender = ScheduleAdmissionLockCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-b"),
        ttl=Duration.seconds(5),
    )
    reacquired = contender.acquire(
        schedule_id=schedule_id,
        now=_instant(),
    )

    assert reacquired.acquired is True
    assert reacquired.handle is not None
    assert reacquired.handle.worker_id == WorkerId("worker-b")
