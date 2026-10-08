"""POST-00E cross-adapter persistence contract.

Every scenario in this module must have the same observable semantics for the
in-memory and SQLite UnitOfWork implementations.
"""

from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.execution import Execution
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
from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory
from pyschedulekit.ports.persistence import ReferentialIntegrityError


_BACKENDS = ("memory", "sqlite")


def _instant(minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, minute, tzinfo=UTC))


def _factory(backend: str, tmp_path):
    if backend == "memory":
        return InMemoryUnitOfWorkFactory()
    if backend == "sqlite":
        return SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    raise AssertionError(f"Unsupported test backend: {backend}")


def _schedule(schedule_id: str = "schedule-1") -> Schedule:
    return Schedule.create(
        schedule_id=ScheduleId(schedule_id),
        definition=ScheduleDefinition(
            target=TargetRef.python(f"jobs:{schedule_id}"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(),
            ),
        ),
        reference=_instant(),
    )


def _request(
    *,
    request_id: str = "request-1",
    schedule_id: str = "schedule-1",
) -> ExecutionRequest:
    return ExecutionRequest(
        id=RequestId(request_id),
        occurrence_key=OccurrenceKey(
            schedule_id=ScheduleId(schedule_id),
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        ),
        target=TargetRef.python("jobs:target"),
        created_at=_instant(),
    )


def _execution_for(request: ExecutionRequest) -> Execution:
    request.mark_dispatched()
    return Execution.from_request(
        request=request,
        created_at=_instant(),
    )


@pytest.mark.parametrize("backend", _BACKENDS)
def test_orphan_request_is_rejected(
    backend: str,
    tmp_path,
) -> None:
    factory = _factory(backend, tmp_path)

    with factory() as uow:
        uow.requests.add(
            _request(
                request_id="orphan-request",
                schedule_id="missing-schedule",
            )
        )
        with pytest.raises(ReferentialIntegrityError):
            uow.commit()


@pytest.mark.parametrize("backend", _BACKENDS)
def test_orphan_execution_is_rejected(
    backend: str,
    tmp_path,
) -> None:
    factory = _factory(backend, tmp_path)
    request = _request(request_id="missing-request")
    execution = _execution_for(request)

    with factory() as uow:
        uow.executions.add(execution)
        with pytest.raises(ReferentialIntegrityError):
            uow.commit()


@pytest.mark.parametrize("backend", _BACKENDS)
def test_orphan_attempt_is_rejected(
    backend: str,
    tmp_path,
) -> None:
    factory = _factory(backend, tmp_path)
    request = _request(request_id="missing-request")
    execution = _execution_for(request)
    attempt = execution.start_attempt(started_at=_instant(minute=1))

    with factory() as uow:
        uow.attempts.add(attempt)
        with pytest.raises(ReferentialIntegrityError):
            uow.commit()


@pytest.mark.parametrize("backend", _BACKENDS)
def test_complete_execution_graph_can_be_committed_in_one_unit_of_work(
    backend: str,
    tmp_path,
) -> None:
    factory = _factory(backend, tmp_path)
    schedule = _schedule()
    request = _request()
    execution = _execution_for(request)
    attempt = execution.start_attempt(started_at=_instant(minute=1))

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.executions.add(execution)
        uow.attempts.add(attempt)
        uow.commit()

    with factory() as uow:
        assert uow.schedules.get(schedule.id) is not None
        assert uow.requests.get(request.id) is not None
        assert uow.executions.get(execution.id) is not None
        assert uow.attempts.get(attempt.id) is not None


@pytest.mark.parametrize("backend", _BACKENDS)
def test_staged_pending_request_is_visible_before_commit(
    backend: str,
    tmp_path,
) -> None:
    factory = _factory(backend, tmp_path)
    schedule = _schedule()
    request = _request()

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)

        assert [item.id for item in uow.requests.list_pending(limit=10)] == [request.id]
        assert uow.requests.has_pending() is True


@pytest.mark.parametrize("backend", _BACKENDS)
def test_staged_queued_execution_is_visible_to_next_runnable_at(
    backend: str,
    tmp_path,
) -> None:
    factory = _factory(backend, tmp_path)
    schedule = _schedule()
    request = _request()
    execution = _execution_for(request)

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.executions.add(execution)

        assert uow.executions.next_runnable_at(now=_instant()) == _instant()
