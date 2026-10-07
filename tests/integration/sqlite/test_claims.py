"""LOT-26 integration tests for durable distributed claims."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from pyschedulekit.application.claims import ExecutionClaimCoordinator
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.domain.claim import (
    ClaimOwnershipError,
    ExecutionClaimState,
    WorkerId,
)
from pyschedulekit.domain.execution_request import ExecutionRequest
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


def _instant(second: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, second, tzinfo=UTC))


def _seed_execution(factory: SqliteUnitOfWorkFactory):
    schedule = Schedule.create(
        schedule_id=ScheduleId("claim-schedule"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:claim"),
            trigger=IntervalTrigger(
                every=Duration.hours(1),
                anchor=Instant(datetime(2026, 1, 1, 11, 0, tzinfo=UTC)),
            ),
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
    )
    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.commit()

    execution = ExecutionService(uow_factory=factory).dispatch(
        request_id=request.id,
        created_at=_instant(),
    )
    return execution


def test_t_claim_sql_001_only_one_worker_acquires_active_claim(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    execution = _seed_execution(factory)
    first = ExecutionClaimCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-a"),
        ttl=Duration.seconds(30),
    )
    second = ExecutionClaimCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-b"),
        ttl=Duration.seconds(30),
    )

    acquired = first.acquire(execution_id=execution.id, now=_instant())
    denied = second.acquire(execution_id=execution.id, now=_instant())

    assert acquired.acquired
    assert acquired.handle is not None
    assert not denied.acquired
    assert denied.reason == "already_claimed"


def test_t_claim_sql_002_expired_claim_can_be_taken_over(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    execution = _seed_execution(factory)
    first = ExecutionClaimCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-a"),
        ttl=Duration.seconds(30),
    )
    second = ExecutionClaimCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-b"),
        ttl=Duration.seconds(30),
    )

    original = first.acquire(execution_id=execution.id, now=_instant())
    takeover = second.acquire(execution_id=execution.id, now=_instant(30))

    assert original.acquired
    assert takeover.acquired
    assert takeover.handle is not None
    assert takeover.handle.worker_id == WorkerId("worker-b")
    assert original.handle is not None
    assert takeover.handle.generation == original.handle.generation + 1


def test_t_claim_sql_003_stale_owner_cannot_start_attempt_after_takeover(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    execution = _seed_execution(factory)
    first = ExecutionClaimCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-a"),
        ttl=Duration.seconds(30),
    )
    second = ExecutionClaimCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-b"),
        ttl=Duration.seconds(30),
    )
    original = first.acquire(execution_id=execution.id, now=_instant())
    takeover = second.acquire(execution_id=execution.id, now=_instant(30))
    assert original.handle is not None
    assert takeover.handle is not None

    service = ExecutionService(uow_factory=factory)
    with pytest.raises(ClaimOwnershipError):
        service.start_attempt(
            execution_id=execution.id,
            started_at=_instant(30),
            claim_handle=original.handle,
        )

    attempt = service.start_attempt(
        execution_id=execution.id,
        started_at=_instant(30),
        claim_handle=takeover.handle,
    )

    assert attempt.number == 1
    with factory() as uow:
        claim = uow.claims.get(execution.id)
        assert claim is not None
        assert claim.state is ExecutionClaimState.ACTIVE
        assert claim.worker_id == WorkerId("worker-b")
        assert claim.generation == takeover.handle.generation

    service.succeed_attempt(
        attempt_id=attempt.id,
        completed_at=_instant(31),
        claim_handle=takeover.handle,
    )

    with factory() as uow:
        released = uow.claims.get(execution.id)
        assert released is not None
        assert released.state is ExecutionClaimState.RELEASED


def test_t_claim_sql_004_v3_database_migrates_through_current_schema(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    SqliteUnitOfWorkFactory(database)

    connection = sqlite3.connect(database)
    try:
        connection.execute("DROP INDEX ix_schedule_materialization_leases_active")
        connection.execute("DROP TABLE schedule_materialization_leases")
        connection.execute("DROP INDEX ix_schedule_admission_locks_active")
        connection.execute("DROP TABLE schedule_admission_locks")
        connection.execute("DROP INDEX ix_execution_claims_active")
        connection.execute("DROP TABLE execution_claims")
        connection.execute("UPDATE pyschedulekit_schema SET version = 3")
        connection.commit()
    finally:
        connection.close()

    SqliteUnitOfWorkFactory(database)

    connection = sqlite3.connect(database)
    try:
        version = connection.execute("SELECT version FROM pyschedulekit_schema").fetchone()
        table = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'execution_claims'
            """
        ).fetchone()

        assert version is not None
        assert int(version[0]) == 7
        assert table is not None
    finally:
        connection.close()
