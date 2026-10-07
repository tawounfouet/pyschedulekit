"""LOT-27 integration tests for multi-worker admission."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from pyschedulekit.application.admission_lock import ScheduleAdmissionLockCoordinator
from pyschedulekit.application.concurrency import ConcurrencyCoordinator
from pyschedulekit.domain.admission_lock import ScheduleAdmissionLockState
from pyschedulekit.domain.claim import WorkerId
from pyschedulekit.domain.concurrency import ConcurrencyDecisionAction, ConcurrencyPolicy
from pyschedulekit.domain.execution import Execution
from pyschedulekit.domain.execution_request import ExecutionRequest, ExecutionRequestState
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
from pyschedulekit.ports.persistence import OptimisticConcurrencyError


def _instant(minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, minute, tzinfo=UTC))


def _seed(factory: SqliteUnitOfWorkFactory) -> tuple[ExecutionRequest, ExecutionRequest]:
    schedule = Schedule.create(
        schedule_id=ScheduleId("shared"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:shared"),
            trigger=IntervalTrigger(
                every=Duration.hours(1),
                anchor=_instant(10),
            ),
            concurrency=ConcurrencyPolicy.limit(max_instances=1),
        ),
        reference=Instant(datetime(2026, 1, 1, 9, 0, tzinfo=UTC)),
    )
    requests: list[ExecutionRequest] = []
    for minute in (0, 1):
        occurrence = Occurrence(
            schedule_id=schedule.id,
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(minute),
        )
        requests.append(
            ExecutionRequest.from_occurrence(
                occurrence=occurrence,
                target=schedule.definition.target,
                created_at=_instant(minute),
                concurrency_policy=schedule.definition.concurrency,
            )
        )

    with factory() as uow:
        uow.schedules.add(schedule)
        for request in requests:
            uow.requests.add(request)
        uow.commit()

    return requests[0], requests[1]


def _coordinator(
    factory: SqliteUnitOfWorkFactory,
    worker: str,
) -> ConcurrencyCoordinator:
    return ConcurrencyCoordinator(
        uow_factory=factory,
        admission_lock_coordinator=ScheduleAdmissionLockCoordinator(
            uow_factory=factory,
            worker_id=WorkerId(worker),
            ttl=Duration.seconds(5),
        ),
    )


def test_t_admission_sql_001_two_workers_preserve_global_limit(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)
    first, second = _seed(factory)
    pairs = (
        (_coordinator(SqliteUnitOfWorkFactory(database), "worker-a"), first),
        (_coordinator(SqliteUnitOfWorkFactory(database), "worker-b"), second),
    )

    def admit(pair):
        coordinator, request = pair
        return coordinator.admit(request_id=request.id, created_at=_instant(2))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(admit, pairs))

    admitted = [result for result in results if result.execution is not None]
    assert len(admitted) == 1

    with factory() as uow:
        assert uow.executions.count_non_terminal_for_schedule(ScheduleId("shared")) == 1
        first_state = uow.requests.get(first.id).state  # type: ignore[union-attr]
        second_state = uow.requests.get(second.id).state  # type: ignore[union-attr]

    states = {first_state, second_state}
    assert ExecutionRequestState.DISPATCHED in states
    assert states <= {
        ExecutionRequestState.DISPATCHED,
        ExecutionRequestState.PENDING,
        ExecutionRequestState.WAITING_ADMISSION,
    }

    pending_request = first if first_state is ExecutionRequestState.PENDING else second
    if ExecutionRequestState.PENDING in states:
        queued = _coordinator(
            SqliteUnitOfWorkFactory(database),
            "worker-c",
        ).admit(
            request_id=pending_request.id,
            created_at=_instant(3),
        )
        assert queued.action is ConcurrencyDecisionAction.QUEUE
        assert not queued.lock_denied
        with factory() as uow:
            persisted = uow.requests.get(pending_request.id)
            assert persisted is not None
            assert persisted.state is ExecutionRequestState.WAITING_ADMISSION


def test_t_admission_sql_002_active_lock_denies_without_mutating_request(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)
    first, _ = _seed(factory)
    holder = ScheduleAdmissionLockCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("holder"),
        ttl=Duration.seconds(5),
    )
    held = holder.acquire(schedule_id=ScheduleId("shared"), now=_instant(2))
    assert held.acquired

    result = _coordinator(
        SqliteUnitOfWorkFactory(database),
        "worker-b",
    ).admit(request_id=first.id, created_at=_instant(2))

    assert result.lock_denied
    assert result.execution is None
    with factory() as uow:
        request = uow.requests.get(first.id)
        assert request is not None
        assert request.state is ExecutionRequestState.PENDING


def test_t_admission_sql_003_expired_lock_can_be_recovered(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)
    first, _ = _seed(factory)
    holder = ScheduleAdmissionLockCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-a"),
        ttl=Duration.seconds(5),
    )
    held = holder.acquire(schedule_id=ScheduleId("shared"), now=_instant())
    assert held.acquired

    result = _coordinator(
        SqliteUnitOfWorkFactory(database),
        "worker-b",
    ).admit(request_id=first.id, created_at=Instant(datetime(2026, 1, 1, 10, 0, 5, tzinfo=UTC)))

    assert result.action is ConcurrencyDecisionAction.ADMIT
    assert result.execution is not None


def test_t_admission_sql_004_v4_database_migrates_through_current_schema(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    SqliteUnitOfWorkFactory(database)

    connection = sqlite3.connect(database)
    try:
        connection.execute("DROP INDEX ix_schedule_materialization_leases_active")
        connection.execute("DROP TABLE schedule_materialization_leases")
        connection.execute("DROP INDEX ix_schedule_admission_locks_active")
        connection.execute("DROP TABLE schedule_admission_locks")
        connection.execute("ALTER TABLE execution_claims DROP COLUMN generation")
        connection.execute("DROP INDEX IF EXISTS ix_executions_retention")
        connection.execute("DROP INDEX IF EXISTS ix_execution_requests_retention")
        connection.execute("DROP INDEX IF EXISTS ix_outbox_published")
        connection.execute("ALTER TABLE executions DROP COLUMN completed_at")
        connection.execute("UPDATE pyschedulekit_schema SET version = 4")
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
            WHERE type = 'table' AND name = 'schedule_admission_locks'
            """
        ).fetchone()
        assert version is not None
        assert int(version[0]) == 8
        assert table is not None
    finally:
        connection.close()


def test_t_admission_sql_005_stale_generation_rolls_back_admission_write(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)
    first, _ = _seed(factory)
    owner = ScheduleAdmissionLockCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-a"),
        ttl=Duration.seconds(5),
    )
    acquired = owner.acquire(
        schedule_id=ScheduleId("shared"),
        now=_instant(),
    )
    assert acquired.handle is not None

    stale_factory = SqliteUnitOfWorkFactory(database)
    stale_uow = stale_factory()
    with stale_uow:
        request = stale_uow.requests.get(first.id)
        lock = stale_uow.admission_locks.get(ScheduleId("shared"))
        assert request is not None
        assert lock is not None

        request.mark_dispatched()
        stale_uow.requests.save(request)
        stale_uow.executions.add(
            Execution.from_request(
                request=request,
                created_at=_instant(1),
            )
        )

        contender = ScheduleAdmissionLockCoordinator(
            uow_factory=SqliteUnitOfWorkFactory(database),
            worker_id=WorkerId("worker-b"),
            ttl=Duration.seconds(5),
        )
        takeover = contender.acquire(
            schedule_id=ScheduleId("shared"),
            now=Instant(datetime(2026, 1, 1, 10, 0, 5, tzinfo=UTC)),
        )
        assert takeover.handle is not None
        assert takeover.handle.generation == acquired.handle.generation + 1

        lock.release(
            worker_id=acquired.handle.worker_id,
            token=acquired.handle.token,
            generation=acquired.handle.generation,
            released_at=Instant(datetime(2026, 1, 1, 10, 0, 1, tzinfo=UTC)),
        )
        stale_uow.admission_locks.save(lock)

        with pytest.raises(OptimisticConcurrencyError):
            stale_uow.commit()

    with factory() as uow:
        request = uow.requests.get(first.id)
        current_lock = uow.admission_locks.get(ScheduleId("shared"))
        assert request is not None
        assert current_lock is not None
        assert request.state is ExecutionRequestState.PENDING
        assert uow.executions.get_by_request(first.id) is None
        assert current_lock.state is ScheduleAdmissionLockState.ACTIVE
        assert current_lock.worker_id == WorkerId("worker-b")
        assert current_lock.generation == acquired.handle.generation + 1
