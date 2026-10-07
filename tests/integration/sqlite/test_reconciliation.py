"""LOT-24 integration tests for durable graph reconciliation."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from pyschedulekit import ReconciliationIncompleteError, RetryPolicy, Scheduler
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.application.reconciliation import ReconciliationService
from pyschedulekit.domain.execution import ExecutionState
from pyschedulekit.domain.execution_request import (
    ExecutionRequest,
    ExecutionRequestState,
)
from pyschedulekit.domain.occurrence import Occurrence
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleRevision,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _seed_request(
    factory: SqliteUnitOfWorkFactory,
    *,
    schedule_id: str = "reconciliation-schedule",
) -> tuple[Schedule, ExecutionRequest]:
    schedule = Schedule.create(
        schedule_id=ScheduleId(schedule_id),
        definition=ScheduleDefinition(
            target=TargetRef.python(f"jobs:{schedule_id}"),
            trigger=IntervalTrigger(
                every=Duration.hours(1),
                anchor=_instant(hour=11),
            ),
            retry=RetryPolicy.none(),
        ),
        reference=_instant(hour=9),
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
        retry_policy=schedule.definition.retry,
    )

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.commit()

    return schedule, request


def test_t_reconciliation_001_dispatched_request_without_execution_is_reconstructed(
    tmp_path,
) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    _, request = _seed_request(factory)

    with factory() as uow:
        loaded = uow.requests.get(request.id)
        assert loaded is not None
        loaded.mark_dispatched()
        uow.requests.save(loaded)
        uow.commit()

    result = ReconciliationService(uow_factory=factory).reconcile()

    assert result.complete is True
    assert len(result.reconstructed_execution_ids) == 1
    assert result.issues == ()

    with factory() as uow:
        execution = uow.executions.get_by_request(request.id)
        assert execution is not None
        assert execution.state is ExecutionState.QUEUED
        assert execution.request_id == request.id
        assert execution.target == request.target


def test_t_reconciliation_002_existing_execution_repairs_request_to_dispatched(
    tmp_path,
) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)
    _, request = _seed_request(factory)
    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(
        request_id=request.id,
        created_at=_instant(),
    )

    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """
            UPDATE execution_requests
            SET state = ?, version = version + 1
            WHERE id = ?
            """,
            (ExecutionRequestState.PENDING.value, request.id.value),
        )
        connection.commit()
    finally:
        connection.close()

    result = ReconciliationService(uow_factory=factory).reconcile()

    assert result.complete is True
    assert result.repaired_request_ids == (request.id,)

    with factory() as uow:
        repaired = uow.requests.get(request.id)
        persisted_execution = uow.executions.get(execution.id)
        assert repaired is not None
        assert persisted_execution is not None
        assert repaired.state is ExecutionRequestState.DISPATCHED


def test_t_reconciliation_003_terminal_request_with_execution_is_not_guessed(
    tmp_path,
) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)
    _, request = _seed_request(factory)
    execution = ExecutionService(uow_factory=factory).dispatch(
        request_id=request.id,
        created_at=_instant(),
    )

    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """
            UPDATE execution_requests
            SET state = ?, version = version + 1
            WHERE id = ?
            """,
            (ExecutionRequestState.CANCELLED.value, request.id.value),
        )
        connection.commit()
    finally:
        connection.close()

    result = ReconciliationService(uow_factory=factory).reconcile()

    assert result.complete is False
    assert result.repaired == 0
    assert any(
        issue.code == "reconciliation.terminal_request_has_execution"
        and issue.execution_id == execution.id
        for issue in result.issues
    )


def test_t_reconciliation_004_missing_attempt_history_is_reported(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)
    _, request = _seed_request(factory)
    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(
        request_id=request.id,
        created_at=_instant(),
    )
    attempt = service.start_attempt(
        execution_id=execution.id,
        started_at=_instant(),
    )
    service.succeed_attempt(
        attempt_id=attempt.id,
        completed_at=_instant(minute=1),
    )

    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "DELETE FROM attempts WHERE id = ?",
            (attempt.id.value,),
        )
        connection.commit()
    finally:
        connection.close()

    result = ReconciliationService(uow_factory=factory).reconcile()

    assert result.complete is False
    assert any(
        issue.code == "reconciliation.attempt_history_mismatch"
        and issue.execution_id == execution.id
        for issue in result.issues
    )
    assert any(
        issue.code == "reconciliation.terminal_history_mismatch"
        and issue.execution_id == execution.id
        for issue in result.issues
    )


def test_t_reconciliation_005_bounded_scan_fails_closed_when_truncated(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    _seed_request(factory, schedule_id="schedule-a")
    _seed_request(factory, schedule_id="schedule-b")

    result = ReconciliationService(uow_factory=factory).reconcile(limit=1)

    assert result.scan_truncated is True
    assert result.complete is False
    assert result.scanned_requests == 1


def test_t_reconciliation_006_scheduler_reconciles_before_first_cycle(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    _, request = _seed_request(factory)

    with factory() as uow:
        loaded = uow.requests.get(request.id)
        assert loaded is not None
        loaded.mark_dispatched()
        uow.requests.save(loaded)
        uow.commit()

    scheduler = Scheduler(
        clock=MutableClock(_instant(minute=1)),
        uow_factory=factory,
    )
    scheduler.run_pending()

    assert scheduler.last_reconciliation_result is not None
    assert scheduler.last_reconciliation_result.complete is True
    assert len(scheduler.last_reconciliation_result.reconstructed_execution_ids) == 1


def test_t_reconciliation_007_scheduler_blocks_on_unsafe_drift(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)
    _, request = _seed_request(factory)
    ExecutionService(uow_factory=factory).dispatch(
        request_id=request.id,
        created_at=_instant(),
    )

    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """
            UPDATE execution_requests
            SET state = ?, version = version + 1
            WHERE id = ?
            """,
            (ExecutionRequestState.DROPPED.value, request.id.value),
        )
        connection.commit()
    finally:
        connection.close()

    scheduler = Scheduler(
        clock=MutableClock(_instant(minute=1)),
        uow_factory=factory,
    )

    with pytest.raises(ReconciliationIncompleteError) as captured:
        scheduler.run_pending()

    assert captured.value.result.complete is False
    assert scheduler.last_reconciliation_result == captured.value.result
