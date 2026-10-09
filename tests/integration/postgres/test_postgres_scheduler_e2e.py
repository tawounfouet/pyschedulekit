"""PG-04 Scheduler and multi-worker E2E qualification on live PostgreSQL."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import psycopg
import pytest

from pyschedulekit import (
    ConcurrencyPolicy,
    Duration,
    FixedBackoff,
    IntervalTrigger,
    RetryPolicy,
    Scheduler,
)
from pyschedulekit.application.admission_lock import ScheduleAdmissionLockCoordinator
from pyschedulekit.application.claims import ExecutionClaimCoordinator
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.application.materialization import ScheduleMaterializationCoordinator
from pyschedulekit.domain.claim import ExecutionClaimState, WorkerId
from pyschedulekit.domain.execution import AttemptState, ExecutionState
from pyschedulekit.domain.execution_request import (
    ExecutionRequest,
    ExecutionRequestState,
)
from pyschedulekit.domain.occurrence import Occurrence
from pyschedulekit.domain.outbox import OutboxMessage, OutboxState
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleRevision,
    TargetRef,
)
from pyschedulekit.domain.time import Instant
from pyschedulekit.infrastructure.postgres import PostgresUnitOfWorkFactory
from pyschedulekit.testing import MutableClock

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


def _instant(
    *,
    hour: int = 10,
    minute: int = 0,
    second: int = 0,
) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, second, tzinfo=UTC))


def _factory() -> PostgresUnitOfWorkFactory:
    assert POSTGRES_DSN is not None
    return PostgresUnitOfWorkFactory(POSTGRES_DSN)


class _RecordingPublisher:
    def __init__(self) -> None:
        self.messages: list[OutboxMessage] = []

    def publish(self, message: OutboxMessage) -> None:
        self.messages.append(message)


def test_pg04_scheduler_run_pending_is_durable_on_postgres() -> None:
    factory = _factory()
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock, uow_factory=factory)
    calls: list[str] = []

    scheduler.add_schedule(
        id="postgres-runtime",
        target=lambda: calls.append("ran"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(minute=10),
        ),
    )

    clock.advance(Duration.minutes(10))
    result = scheduler.run_pending()

    assert calls == ["ran"]
    assert result.succeeded == 1
    assert len(result.executions) == 1
    assert result.executions[0].execution.state is ExecutionState.SUCCESS

    reopened = _factory()
    with reopened() as uow:
        schedule = uow.schedules.get(ScheduleId("postgres-runtime"))
        assert schedule is not None
        assert schedule.next_run_time == _instant(minute=20)


def test_pg04_retry_succeeds_after_postgres_backoff() -> None:
    factory = _factory()
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock, uow_factory=factory)
    calls = 0

    def target() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary")

    scheduler.add_schedule(
        id="postgres-retry",
        target=target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(minute=10),
        ),
        retry=RetryPolicy(
            max_attempts=3,
            backoff=FixedBackoff(Duration.minutes(5)),
        ),
    )

    clock.advance(Duration.minutes(10))
    first = scheduler.run_pending()

    assert calls == 1
    assert first.retry_scheduled == 1
    assert first.executions[0].execution.state is ExecutionState.RETRY_WAIT

    before_deadline = scheduler.run_pending()
    assert before_deadline.executions == ()
    assert calls == 1

    clock.advance(Duration.minutes(5))
    second = scheduler.run_pending()

    assert calls == 2
    assert second.succeeded == 1
    assert second.executions[0].execution.state is ExecutionState.SUCCESS
    assert second.executions[0].execution.attempt_count == 2


def test_pg04_outbox_dispatches_postgres_lifecycle_messages() -> None:
    factory = _factory()
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock, uow_factory=factory)
    calls: list[str] = []

    scheduler.add_schedule(
        id="postgres-outbox",
        target=lambda: calls.append("ran"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(minute=10),
        ),
    )

    clock.advance(Duration.minutes(10))
    result = scheduler.run_pending()
    assert result.succeeded == 1
    assert calls == ["ran"]

    with factory() as uow:
        pending = uow.outbox.list_pending(limit=10)

    assert [message.event_type for message in pending] == [
        "execution.attempt.started",
        "execution.attempt.completed",
    ]
    assert all(message.state is OutboxState.PENDING for message in pending)

    publisher = _RecordingPublisher()
    dispatch = scheduler.dispatch_outbox(publisher)

    assert dispatch.published == 2
    assert dispatch.failed == 0
    assert [message.event_type for message in publisher.messages] == [
        "execution.attempt.started",
        "execution.attempt.completed",
    ]

    with factory() as uow:
        assert uow.outbox.list_pending(limit=10) == []


def test_pg04_reconciliation_reconstructs_missing_execution_on_postgres() -> None:
    factory = _factory()
    schedule = Schedule.create(
        schedule_id=ScheduleId("postgres-reconcile"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:postgres-reconcile"),
            trigger=IntervalTrigger(
                every=Duration.hours(1),
                anchor=_instant(hour=11),
            ),
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
    )
    request.mark_dispatched()

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.commit()

    calls: list[str] = []
    scheduler = Scheduler(
        clock=MutableClock(_instant(minute=1)),
        uow_factory=_factory(),
    )
    scheduler.register_target(
        "jobs:postgres-reconcile",
        lambda: calls.append("ran"),
    )

    result = scheduler.run_pending()

    assert scheduler.last_reconciliation_result is not None
    assert scheduler.last_reconciliation_result.complete is True
    assert len(scheduler.last_reconciliation_result.reconstructed_execution_ids) == 1
    assert calls == ["ran"]
    assert result.succeeded == 1
    assert result.executions[0].execution.state is ExecutionState.SUCCESS


def test_pg04_restart_recovers_then_retry_succeeds_on_postgres() -> None:
    factory = _factory()
    retry = RetryPolicy(
        max_attempts=2,
        backoff=FixedBackoff(Duration.minutes(5)),
    )
    schedule = Schedule.create(
        schedule_id=ScheduleId("postgres-recovery"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:postgres-recovery"),
            trigger=IntervalTrigger(
                every=Duration.hours(1),
                anchor=_instant(hour=11),
            ),
            retry=retry,
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
        retry_policy=retry,
    )

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.commit()

    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(
        request_id=request.id,
        created_at=_instant(),
    )
    service.start_attempt(
        execution_id=execution.id,
        started_at=_instant(),
    )

    clock = MutableClock(_instant(minute=1))
    restarted = Scheduler(
        clock=clock,
        uow_factory=_factory(),
    )
    calls: list[str] = []
    restarted.register_target(
        "jobs:postgres-recovery",
        lambda: calls.append("attempt-2"),
    )

    first = restarted.run_pending()

    assert calls == []
    assert first.executions == ()
    assert restarted.last_recovery_result is not None
    assert restarted.last_recovery_result.retried_execution_ids == (execution.id,)

    clock.advance(Duration.minutes(5))
    second = restarted.run_pending()

    assert calls == ["attempt-2"]
    assert second.succeeded == 1
    assert second.executions[0].execution.state is ExecutionState.SUCCESS

    with factory() as uow:
        recovered = uow.executions.get(execution.id)
        attempts = uow.attempts.list_for_execution(execution.id)

        assert recovered is not None
        assert recovered.state is ExecutionState.SUCCESS
        assert recovered.attempt_count == 2
        assert [attempt.state for attempt in attempts] == [
            AttemptState.FAILED,
            AttemptState.SUCCESS,
        ]
        assert attempts[0].result is not None
        assert attempts[0].result.failure is not None
        assert attempts[0].result.failure.code == "execution.crash_recovered"


def test_pg04_scheduler_reports_postgres_admission_lock_contention() -> None:
    factory = _factory()
    clock = MutableClock(_instant())

    owner = Scheduler(
        clock=clock,
        uow_factory=factory,
        worker_id="worker-a",
    )
    owner.add_schedule(
        id="postgres-admission",
        target=lambda: None,
        trigger=IntervalTrigger(
            every=Duration.hours(1),
            anchor=_instant(hour=11),
        ),
        concurrency=ConcurrencyPolicy.limit(max_instances=1),
    )

    with factory() as uow:
        schedule = uow.schedules.get(ScheduleId("postgres-admission"))
        assert schedule is not None
        occurrence = Occurrence(
            schedule_id=schedule.id,
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        )
        request = ExecutionRequest.from_occurrence(
            occurrence=occurrence,
            target=schedule.definition.target,
            created_at=_instant(),
            concurrency_policy=schedule.definition.concurrency,
        )
        uow.requests.add(request)
        uow.commit()

    holder = ScheduleAdmissionLockCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-a"),
        ttl=Duration.seconds(5),
    )
    held = holder.acquire(
        schedule_id=ScheduleId("postgres-admission"),
        now=_instant(),
    )
    assert held.acquired

    contender = Scheduler(
        clock=clock,
        uow_factory=_factory(),
        worker_id="worker-b",
    )
    contender.register_target("local:postgres-admission", lambda: None)
    result = contender.run_pending()

    assert result.admission_lock_denied_request_ids == (request.id,)
    assert result.queued_request_ids == ()
    assert result.executions == ()

    with factory() as uow:
        persisted = uow.requests.get(request.id)
        assert persisted is not None
        assert persisted.state is ExecutionRequestState.PENDING
        assert uow.executions.get_by_request(request.id) is None


def test_pg04_scheduler_reports_postgres_materialization_contention() -> None:
    factory = _factory()
    clock = MutableClock(_instant())
    owner = Scheduler(
        clock=clock,
        uow_factory=factory,
        worker_id="worker-a",
    )
    owner.add_schedule(
        id="postgres-materialization",
        target=lambda: None,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(minute=10),
        ),
    )

    clock.advance(Duration.minutes(10))
    holder = ScheduleMaterializationCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-a"),
        ttl=Duration.seconds(30),
    )
    held = holder.acquire(
        schedule_id=ScheduleId("postgres-materialization"),
        now=clock.now(),
    )
    assert held.acquired

    contender = Scheduler(
        clock=clock,
        uow_factory=_factory(),
        worker_id="worker-b",
    )
    contender.register_target("local:postgres-materialization", lambda: None)
    result = contender.run_pending()

    assert result.materialization_denied_schedule_ids == (
        ScheduleId("postgres-materialization"),
    )
    assert result.materialized_request_ids == ()
    assert result.executions == ()


def test_pg04_second_worker_recovers_expired_postgres_claim() -> None:
    factory = _factory()
    schedule = Schedule.create(
        schedule_id=ScheduleId("postgres-orphan"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:postgres-orphan"),
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
        retry_policy=RetryPolicy.none(),
    )

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.commit()

    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(
        request_id=request.id,
        created_at=_instant(),
    )
    owner = ExecutionClaimCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-a"),
        ttl=Duration.seconds(30),
    )
    acquired = owner.acquire(
        execution_id=execution.id,
        now=_instant(),
    )
    assert acquired.handle is not None
    attempt = service.start_attempt(
        execution_id=execution.id,
        started_at=_instant(),
        claim_handle=acquired.handle,
    )

    clock = MutableClock(_instant(second=10))
    worker_b = Scheduler(
        clock=clock,
        uow_factory=_factory(),
        worker_id="worker-b",
        claim_ttl=Duration.seconds(30),
    )

    first = worker_b.run_pending()

    assert first.executions == ()
    with factory() as uow:
        protected = uow.executions.get(execution.id)
        assert protected is not None
        assert protected.state is ExecutionState.RUNNING

    clock.set(_instant(second=30))
    second = worker_b.run_pending()

    assert second.executions == ()
    with factory() as uow:
        recovered = uow.executions.get(execution.id)
        recovered_attempt = uow.attempts.get(attempt.id)
        claim = uow.claims.get(execution.id)

        assert recovered is not None
        assert recovered_attempt is not None
        assert claim is not None
        assert recovered.state is ExecutionState.FAILED
        assert recovered_attempt.state is AttemptState.FAILED
        assert claim.state is ExecutionClaimState.RELEASED
        assert claim.worker_id == WorkerId("worker-b")
        assert claim.generation == acquired.handle.generation + 1
