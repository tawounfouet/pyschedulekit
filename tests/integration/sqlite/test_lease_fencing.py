"""LOT-28 integration tests for renewable execution leases and fencing."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from pyschedulekit.application.claims import ExecutionClaimCoordinator
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.application.recovery import CrashRecoveryService
from pyschedulekit.domain.claim import ClaimOwnershipError, ExecutionClaimState, WorkerId
from pyschedulekit.domain.execution import AttemptState, ExecutionState
from pyschedulekit.domain.execution_request import ExecutionRequest
from pyschedulekit.domain.occurrence import Occurrence
from pyschedulekit.domain.retry import RetryPolicy
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


def _instant(second: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, second, tzinfo=UTC))


def _seed_execution(factory: SqliteUnitOfWorkFactory):
    schedule = Schedule.create(
        schedule_id=ScheduleId("lease-schedule"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:lease"),
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
    execution = service.dispatch(request_id=request.id, created_at=_instant())
    return service, execution


def test_t_lease_sql_001_renew_preserves_generation_and_blocks_takeover(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    _, execution = _seed_execution(factory)
    owner = ExecutionClaimCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-a"),
        ttl=Duration.seconds(30),
    )
    contender = ExecutionClaimCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-b"),
        ttl=Duration.seconds(30),
    )

    acquired = owner.acquire(execution_id=execution.id, now=_instant())
    assert acquired.handle is not None

    renewed = owner.renew(handle=acquired.handle, renewed_at=_instant(20))
    assert renewed is not None
    assert renewed.generation == acquired.handle.generation
    assert renewed.expires_at == _instant(50)

    denied = contender.acquire(execution_id=execution.id, now=_instant(30))
    assert not denied.acquired
    assert denied.reason == "already_claimed"

    takeover = contender.acquire(execution_id=execution.id, now=_instant(50))
    assert takeover.handle is not None
    assert takeover.handle.generation == renewed.generation + 1


def test_t_lease_sql_002_active_lease_protects_running_from_recovery(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    service, execution = _seed_execution(factory)
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

    recovery_clock = MutableClock(_instant(10))
    recovery = CrashRecoveryService(
        clock=recovery_clock,
        uow_factory=factory,
        claim_coordinator=ExecutionClaimCoordinator(
            uow_factory=factory,
            worker_id=WorkerId("worker-b"),
            ttl=Duration.seconds(30),
        ),
    )

    protected = recovery.recover()

    assert protected.complete is True
    assert protected.protected_execution_ids == (execution.id,)
    assert protected.recovered_execution_ids == ()
    assert protected.remaining_running_execution_ids == ()

    with factory() as uow:
        persisted = uow.executions.get(execution.id)
        persisted_attempt = uow.attempts.get(attempt.id)
        assert persisted is not None
        assert persisted_attempt is not None
        assert persisted.state is ExecutionState.RUNNING
        assert persisted_attempt.state is AttemptState.RUNNING


def test_t_lease_sql_003_expired_recovery_fences_stale_completion(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    service, execution = _seed_execution(factory)
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

    recovery = CrashRecoveryService(
        clock=MutableClock(_instant(30)),
        uow_factory=factory,
        claim_coordinator=ExecutionClaimCoordinator(
            uow_factory=factory,
            worker_id=WorkerId("worker-b"),
            ttl=Duration.seconds(30),
        ),
    )
    recovered = recovery.recover()

    assert recovered.failed_execution_ids == (execution.id,)
    assert recovered.protected_execution_ids == ()

    with pytest.raises(ClaimOwnershipError):
        service.succeed_attempt(
            attempt_id=attempt.id,
            completed_at=_instant(31),
            claim_handle=acquired.handle,
        )

    with factory() as uow:
        persisted = uow.executions.get(execution.id)
        claim = uow.claims.get(execution.id)
        assert persisted is not None
        assert claim is not None
        assert persisted.state is ExecutionState.FAILED
        assert claim.state is ExecutionClaimState.RELEASED
        assert claim.generation == acquired.handle.generation + 1


def test_t_lease_sql_004_v5_database_migrates_to_v6(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    SqliteUnitOfWorkFactory(database)

    connection = sqlite3.connect(database)
    try:
        connection.execute("ALTER TABLE execution_claims DROP COLUMN generation")
        connection.execute("ALTER TABLE schedule_admission_locks DROP COLUMN generation")
        connection.execute("UPDATE pyschedulekit_schema SET version = 5")
        connection.commit()
    finally:
        connection.close()

    SqliteUnitOfWorkFactory(database)

    connection = sqlite3.connect(database)
    try:
        version = connection.execute("SELECT version FROM pyschedulekit_schema").fetchone()
        claim_columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(execution_claims)").fetchall()
        }
        admission_columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(schedule_admission_locks)"
            ).fetchall()
        }
        assert version is not None
        assert int(version[0]) == 6
        assert "generation" in claim_columns
        assert "generation" in admission_columns
    finally:
        connection.close()
