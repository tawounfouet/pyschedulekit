"""LOT-27 integration tests for multi-worker admission."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from pyschedulekit.application.admission_lock import ScheduleAdmissionLockCoordinator
from pyschedulekit.application.concurrency import ConcurrencyCoordinator
from pyschedulekit.domain.claim import WorkerId
from pyschedulekit.domain.concurrency import ConcurrencyDecisionAction, ConcurrencyPolicy
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

    actions = sorted(result.action.value for result in results)
    assert actions == ["admit", "queue"]

    with factory() as uow:
        assert uow.executions.count_non_terminal_for_schedule(ScheduleId("shared")) == 1
        states = sorted(
            (
                uow.requests.get(first.id).state,  # type: ignore[union-attr]
                uow.requests.get(second.id).state,  # type: ignore[union-attr]
            ),
            key=str,
        )
        assert states == [
            ExecutionRequestState.DISPATCHED,
            ExecutionRequestState.WAITING_ADMISSION,
        ]


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


def test_t_admission_sql_004_v4_database_migrates_to_v5(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    SqliteUnitOfWorkFactory(database)

    connection = sqlite3.connect(database)
    try:
        connection.execute("DROP INDEX ix_schedule_admission_locks_active")
        connection.execute("DROP TABLE schedule_admission_locks")
        connection.execute("UPDATE pyschedulekit_schema SET version = 4")
        connection.commit()
    finally:
        connection.close()

    SqliteUnitOfWorkFactory(database)

    connection = sqlite3.connect(database)
    try:
        version = connection.execute(
            "SELECT version FROM pyschedulekit_schema"
        ).fetchone()
        table = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'schedule_admission_locks'
            """
        ).fetchone()
        assert version is not None
        assert int(version[0]) == 5
        assert table is not None
    finally:
        connection.close()
