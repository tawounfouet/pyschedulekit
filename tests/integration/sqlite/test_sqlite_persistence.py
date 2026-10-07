"""LOT-21 integration tests for SQLite persistence parity."""

from datetime import UTC, datetime

import pytest

from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.domain.execution import AttemptState, ExecutionState
from pyschedulekit.domain.execution_request import ExecutionRequest
from pyschedulekit.domain.occurrence import Occurrence
from pyschedulekit.domain.schedule import (
    PersistenceVersion,
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleRevision,
    ScheduleState,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory
from pyschedulekit.ports.persistence import (
    DuplicateScheduleError,
    OptimisticConcurrencyError,
)


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _schedule(schedule_id: str, *, minute: int = 0) -> Schedule:
    return Schedule.create(
        schedule_id=ScheduleId(schedule_id),
        definition=ScheduleDefinition(
            target=TargetRef.python(f"jobs:{schedule_id}"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(minute=minute),
            ),
        ),
        reference=_instant(hour=9),
    )


def test_t_sql_001_schedule_commit_round_trip_and_identity_map(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    original = _schedule("schedule-a")

    with factory() as uow:
        uow.schedules.add(original)
        assert uow.schedules.get(original.id) is original
        uow.commit()

    with factory() as uow:
        loaded = uow.schedules.get(original.id)
        again = uow.schedules.get(original.id)

        assert loaded is not None
        assert loaded is again
        assert loaded is not original
        assert loaded.definition == original.definition
        assert loaded.state is ScheduleState.ACTIVE
        assert loaded.persistence_version == PersistenceVersion(0)


def test_t_sql_002_rollback_discards_staged_insert(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")

    with factory() as uow:
        uow.schedules.add(_schedule("schedule-a"))
        uow.rollback()

    with factory() as observer:
        assert observer.schedules.get(ScheduleId("schedule-a")) is None


def test_t_sql_003_duplicate_schedule_is_rejected_at_commit(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")

    with factory() as uow:
        uow.schedules.add(_schedule("schedule-a"))
        uow.commit()

    with factory() as uow:
        uow.schedules.add(_schedule("schedule-a"))
        with pytest.raises(DuplicateScheduleError):
            uow.commit()


def test_t_sql_004_stale_schedule_writer_is_rejected(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")

    with factory() as uow:
        uow.schedules.add(_schedule("schedule-a"))
        uow.commit()

    with factory() as first, factory() as second:
        first_loaded = first.schedules.get(ScheduleId("schedule-a"))
        second_loaded = second.schedules.get(ScheduleId("schedule-a"))
        assert first_loaded is not None
        assert second_loaded is not None

        first_loaded.pause()
        first.schedules.save(first_loaded)
        first.commit()

        second_loaded.cancel()
        second.schedules.save(second_loaded)
        with pytest.raises(OptimisticConcurrencyError):
            second.commit()


def test_t_sql_005_due_query_and_next_run_time(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")

    with factory() as uow:
        uow.schedules.add(_schedule("schedule-b"))
        uow.schedules.add(_schedule("schedule-a"))
        uow.schedules.add(_schedule("future", minute=30))
        uow.commit()

    with factory() as uow:
        due = uow.schedules.list_due(now=_instant(), limit=10)
        next_run = uow.schedules.next_run_time()

        assert [item.id.value for item in due] == ["schedule-a", "schedule-b"]
        assert next_run == _instant()


def test_t_sql_006_execution_graph_round_trip(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    schedule = _schedule("schedule-a")
    occurrence = Occurrence(
        schedule_id=schedule.id,
        schedule_revision=ScheduleRevision(1),
        scheduled_at=_instant(),
    )
    request = ExecutionRequest.from_occurrence(
        occurrence=occurrence,
        target=schedule.definition.target,
        created_at=_instant(),
    )

    with factory() as uow:
        uow.requests.add(request)
        uow.commit()

    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(
        request_id=request.id,
        created_at=_instant(),
    )
    attempt = service.start_attempt(
        execution_id=execution.id,
        started_at=_instant(),
    )
    finished = service.succeed_attempt(
        attempt_id=attempt.id,
        completed_at=_instant(minute=1),
    )

    assert finished.state is ExecutionState.SUCCESS

    with factory() as uow:
        loaded_request = uow.requests.get(request.id)
        loaded_execution = uow.executions.get(execution.id)
        attempts = uow.attempts.list_for_execution(execution.id)

        assert loaded_request is not None
        assert loaded_execution is not None
        assert loaded_execution.state is ExecutionState.SUCCESS
        assert loaded_execution.result is not None
        assert len(attempts) == 1
        assert attempts[0].state is AttemptState.SUCCESS


def test_t_sql_007_shared_memory_database_survives_independent_uow() -> None:
    factory = SqliteUnitOfWorkFactory(":memory:")

    with factory() as uow:
        uow.schedules.add(_schedule("schedule-a"))
        uow.commit()

    with factory() as observer:
        assert observer.schedules.get(ScheduleId("schedule-a")) is not None
