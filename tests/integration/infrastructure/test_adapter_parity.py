"""POST-00E contract tests shared by the in-memory and SQLite adapters."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pyschedulekit.domain.admission_lock import AdmissionToken, ScheduleAdmissionLock
from pyschedulekit.domain.claim import ClaimToken, ExecutionClaim, WorkerId
from pyschedulekit.domain.execution import Execution
from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.materialization_lease import (
    MaterializationToken,
    ScheduleMaterializationLease,
)
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
from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory
from pyschedulekit.ports.persistence import ReferentialIntegrityError, UnitOfWorkFactory


def _instant(*, hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _factory(adapter: str, tmp_path: Path) -> UnitOfWorkFactory:
    if adapter == "memory":
        return InMemoryUnitOfWorkFactory()
    if adapter == "sqlite":
        return SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    raise AssertionError(f"Unknown adapter: {adapter}")


def _schedule(schedule_id: str = "schedule-1") -> Schedule:
    return Schedule.create(
        schedule_id=ScheduleId(schedule_id),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:refresh"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(),
            ),
        ),
        reference=_instant(hour=9),
    )


def _request(
    schedule_id: ScheduleId | None = None,
    *,
    request_id: str = "request-1",
) -> ExecutionRequest:
    effective_schedule_id = schedule_id or ScheduleId("schedule-1")
    return ExecutionRequest(
        id=RequestId(request_id),
        occurrence_key=OccurrenceKey(
            schedule_id=effective_schedule_id,
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        ),
        target=TargetRef.python("jobs:refresh"),
        created_at=_instant(),
    )


def _admission_lock(schedule_id: ScheduleId) -> ScheduleAdmissionLock:
    return ScheduleAdmissionLock(
        schedule_id=schedule_id,
        worker_id=WorkerId("worker-a"),
        token=AdmissionToken("admission-token"),
        acquired_at=_instant(),
        expires_at=_instant(minute=1),
    )


def _materialization_lease(schedule_id: ScheduleId) -> ScheduleMaterializationLease:
    return ScheduleMaterializationLease(
        schedule_id=schedule_id,
        worker_id=WorkerId("worker-a"),
        token=MaterializationToken("materialization-token"),
        acquired_at=_instant(),
        expires_at=_instant(minute=1),
    )


def _claim(execution: Execution) -> ExecutionClaim:
    return ExecutionClaim(
        execution_id=execution.id,
        worker_id=WorkerId("worker-a"),
        token=ClaimToken("claim-token"),
        claimed_at=_instant(),
        expires_at=_instant(minute=1),
    )


@pytest.mark.parametrize("adapter", ("memory", "sqlite"))
@pytest.mark.parametrize(
    "orphan_kind",
    (
        "request",
        "execution",
        "attempt",
        "admission_lock",
        "materialization_lease",
        "claim",
    ),
)
def test_foreign_key_contract_rejects_orphans(
    adapter: str,
    orphan_kind: str,
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)

    with factory() as uow:
        if orphan_kind == "request":
            uow.requests.add(_request())
        elif orphan_kind in ("execution", "attempt", "claim"):
            request = _request()
            request.mark_dispatched()
            execution = Execution.from_request(
                request=request,
                created_at=_instant(),
            )
            if orphan_kind == "execution":
                uow.executions.add(execution)
            elif orphan_kind == "attempt":
                uow.attempts.add(execution.start_attempt(started_at=_instant()))
            else:
                uow.claims.add(_claim(execution))
        elif orphan_kind == "admission_lock":
            uow.admission_locks.add(_admission_lock(ScheduleId("missing-schedule")))
        elif orphan_kind == "materialization_lease":
            uow.materialization_leases.add(_materialization_lease(ScheduleId("missing-schedule")))
        else:
            raise AssertionError(f"Unknown orphan kind: {orphan_kind}")

        with pytest.raises(ReferentialIntegrityError):
            uow.commit()


@pytest.mark.parametrize("adapter", ("memory", "sqlite"))
def test_complete_staged_graph_commits_in_one_transaction(
    adapter: str,
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)
    schedule = _schedule()
    request = _request(schedule.id)
    request.mark_dispatched()
    execution = Execution.from_request(
        request=request,
        created_at=_instant(),
    )
    attempt = execution.start_attempt(started_at=_instant())

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.executions.add(execution)
        uow.attempts.add(attempt)
        uow.admission_locks.add(_admission_lock(schedule.id))
        uow.materialization_leases.add(_materialization_lease(schedule.id))
        uow.claims.add(_claim(execution))
        uow.commit()

    with factory() as uow:
        assert uow.schedules.get(schedule.id) is not None
        assert uow.requests.get(request.id) is not None
        assert uow.executions.get(execution.id) is not None
        assert uow.attempts.get(attempt.id) is not None
        assert uow.admission_locks.get(schedule.id) is not None
        assert uow.materialization_leases.get(schedule.id) is not None
        assert uow.claims.get(execution.id) is not None


@pytest.mark.parametrize("adapter", ("memory", "sqlite"))
def test_staged_queries_observe_uncommitted_work(
    adapter: str,
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)
    pending_request = _request(request_id="pending-request")
    execution_request = _request(
        ScheduleId("execution-schedule"),
        request_id="execution-request",
    )
    execution_request.mark_dispatched()
    execution = Execution.from_request(
        request=execution_request,
        created_at=_instant(),
    )

    with factory() as uow:
        uow.requests.add(pending_request)

        assert uow.requests.has_pending() is True
        assert [item.id for item in uow.requests.list_pending(limit=1)] == [pending_request.id]

        uow.requests.add(execution_request)
        uow.executions.add(execution)

        assert uow.executions.next_runnable_at(now=_instant()) == _instant()
