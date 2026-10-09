"""PG-01 integration qualification for PostgreSQL core repositories."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import psycopg
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
from pyschedulekit.infrastructure.postgres import PostgresUnitOfWorkFactory
from pyschedulekit.ports.persistence import (
    DuplicateScheduleError,
    OptimisticConcurrencyError,
    ReferentialIntegrityError,
)

POSTGRES_DSN = os.getenv("PYSCHEDULEKIT_TEST_POSTGRES_DSN")

pytestmark = pytest.mark.postgres


@pytest.fixture(autouse=True)
def clean_postgres_schema() -> Iterator[None]:
    if POSTGRES_DSN is None:
        pytest.skip("PYSCHEDULEKIT_TEST_POSTGRES_DSN is not configured.")

    with psycopg.connect(POSTGRES_DSN, autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")

    yield

    with psycopg.connect(POSTGRES_DSN, autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")


def _instant(*, hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _factory() -> PostgresUnitOfWorkFactory:
    assert POSTGRES_DSN is not None
    return PostgresUnitOfWorkFactory(POSTGRES_DSN)


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
    schedule_id: ScheduleId,
    *,
    request_id: str = "request-1",
) -> ExecutionRequest:
    return ExecutionRequest(
        id=RequestId(request_id),
        occurrence_key=OccurrenceKey(
            schedule_id=schedule_id,
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        ),
        target=TargetRef.python("jobs:refresh"),
        created_at=_instant(),
    )


def _running_graph() -> tuple[Schedule, ExecutionRequest, Execution, object]:
    schedule = _schedule()
    request = _request(schedule.id)
    request.mark_dispatched()
    execution = Execution.from_request(
        request=request,
        created_at=_instant(),
    )
    attempt = execution.start_attempt(started_at=_instant())
    return schedule, request, execution, attempt


def test_pg01_core_graph_round_trips_atomically_with_identity_map() -> None:
    factory = _factory()
    schedule, request, execution, attempt = _running_graph()

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.executions.add(execution)
        uow.attempts.add(attempt)
        uow.commit()

    with factory() as uow:
        first_schedule = uow.schedules.get(schedule.id)
        second_schedule = uow.schedules.get(schedule.id)
        loaded_request = uow.requests.get(request.id)
        loaded_execution = uow.executions.get(execution.id)
        loaded_attempt = uow.attempts.get(attempt.id)

        assert first_schedule is second_schedule
        assert first_schedule is not None
        assert first_schedule.definition == schedule.definition
        assert first_schedule.next_run_time == schedule.next_run_time
        assert loaded_request == request
        assert loaded_execution is not None
        assert loaded_execution.state == execution.state
        assert loaded_execution.attempt_count == 1
        assert loaded_attempt is not None
        assert loaded_attempt.state == attempt.state

        assert [item.id for item in uow.schedules.list_due(now=_instant(), limit=10)] == [
            schedule.id
        ]
        assert [item.id for item in uow.executions.list_running(limit=10)] == [execution.id]
        assert [item.id for item in uow.attempts.list_for_execution(execution.id)] == [attempt.id]


def test_pg01_rollback_discards_staged_core_state() -> None:
    factory = _factory()
    schedule = _schedule("rollback-schedule")

    with factory() as uow:
        uow.schedules.add(schedule)

    with factory() as uow:
        assert uow.schedules.get(schedule.id) is None


def test_pg01_staged_queries_observe_uncommitted_work() -> None:
    factory = _factory()
    schedule = _schedule("staged-schedule")
    request = _request(schedule.id, request_id="staged-request")
    request.mark_dispatched()
    execution = Execution.from_request(request=request, created_at=_instant())
    attempt = execution.start_attempt(started_at=_instant())

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.executions.add(execution)
        uow.attempts.add(attempt)

        assert [item.id for item in uow.schedules.list_due(now=_instant(), limit=10)] == [
            schedule.id
        ]
        assert uow.requests.get_by_occurrence(request.occurrence_key) is request
        assert uow.executions.get_by_request(request.id) is execution
        assert [item.id for item in uow.executions.list_running(limit=10)] == []
        assert [item.id for item in uow.attempts.list_for_execution(execution.id)] == [attempt.id]


def test_pg01_duplicate_schedule_maps_to_framework_error() -> None:
    factory = _factory()
    first = _schedule("duplicate-schedule")

    with factory() as uow:
        uow.schedules.add(first)
        uow.commit()

    with factory() as uow:
        uow.schedules.add(_schedule("duplicate-schedule"))
        with pytest.raises(DuplicateScheduleError):
            uow.commit()


def test_pg01_foreign_key_violation_maps_to_framework_error() -> None:
    factory = _factory()
    orphan = _request(ScheduleId("missing-schedule"), request_id="orphan-request")

    with factory() as uow:
        uow.requests.add(orphan)
        with pytest.raises(ReferentialIntegrityError):
            uow.commit()


def test_pg01_schedule_compare_and_swap_rejects_lost_update() -> None:
    factory = _factory()
    schedule = _schedule("cas-schedule")

    with factory() as seed:
        seed.schedules.add(schedule)
        seed.commit()

    with factory() as first, factory() as second:
        first_schedule = first.schedules.get(schedule.id)
        second_schedule = second.schedules.get(schedule.id)
        assert first_schedule is not None
        assert second_schedule is not None

        first_schedule.pause()
        first.schedules.save(first_schedule)
        first.commit()

        second_schedule.pause()
        second.schedules.save(second_schedule)
        with pytest.raises(OptimisticConcurrencyError):
            second.commit()


def test_pg01_due_and_runnable_horizons_use_native_postgres_time() -> None:
    factory = _factory()
    schedule = _schedule("horizon-schedule")
    request = _request(schedule.id, request_id="horizon-request")
    request.mark_dispatched()
    execution = Execution.from_request(request=request, created_at=_instant())

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.executions.add(execution)
        uow.commit()

    with factory() as uow:
        assert uow.schedules.next_run_time() == _instant()
        assert uow.executions.next_runnable_at(now=_instant()) == _instant()
        assert [item.id for item in uow.executions.list_runnable(now=_instant(), limit=10)] == [
            execution.id
        ]
