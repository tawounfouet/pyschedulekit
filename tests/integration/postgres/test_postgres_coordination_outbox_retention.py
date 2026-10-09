"""PG-02 integration qualification for PostgreSQL coordination, outbox and retention."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import psycopg
import pytest

from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.application.outbox import OutboxDispatcher, make_outbox_message
from pyschedulekit.domain.admission_lock import (
    AdmissionToken,
    ScheduleAdmissionLock,
    ScheduleAdmissionLockState,
)
from pyschedulekit.domain.claim import (
    ClaimToken,
    ExecutionClaim,
    ExecutionClaimState,
    WorkerId,
)
from pyschedulekit.domain.execution import Attempt, Execution
from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.materialization_lease import (
    MaterializationToken,
    ScheduleMaterializationLease,
    ScheduleMaterializationLeaseState,
)
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.outbox import OutboxMessage, OutboxState
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
    DuplicateAdmissionLockError,
    OptimisticConcurrencyError,
    ReferentialIntegrityError,
)
from pyschedulekit.testing import FixedClock

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


def _instant(*, hour: int = 10, minute: int = 0, second: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, second, tzinfo=UTC))


def _factory() -> PostgresUnitOfWorkFactory:
    assert POSTGRES_DSN is not None
    return PostgresUnitOfWorkFactory(POSTGRES_DSN)


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
        reference=_instant(hour=9),
    )


def _request(schedule: Schedule, *, request_id: str = "request-1") -> ExecutionRequest:
    return ExecutionRequest(
        id=RequestId(request_id),
        occurrence_key=OccurrenceKey(
            schedule_id=schedule.id,
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        ),
        target=schedule.definition.target,
        created_at=_instant(),
    )


def _running_graph() -> tuple[Schedule, ExecutionRequest, Execution, Attempt]:
    schedule = _schedule()
    request = _request(schedule)
    request.mark_dispatched()
    execution = Execution.from_request(request=request, created_at=_instant())
    attempt = execution.start_attempt(started_at=_instant())
    return schedule, request, execution, attempt


def _coordination(
    schedule: Schedule,
    execution: Execution,
) -> tuple[ScheduleAdmissionLock, ScheduleMaterializationLease, ExecutionClaim]:
    worker = WorkerId("worker-a")
    admission = ScheduleAdmissionLock(
        schedule_id=schedule.id,
        worker_id=worker,
        token=AdmissionToken("admission-token"),
        acquired_at=_instant(),
        expires_at=_instant(minute=5),
    )
    materialization = ScheduleMaterializationLease(
        schedule_id=schedule.id,
        worker_id=worker,
        token=MaterializationToken("materialization-token"),
        acquired_at=_instant(),
        expires_at=_instant(minute=5),
    )
    claim = ExecutionClaim(
        execution_id=execution.id,
        worker_id=worker,
        token=ClaimToken("claim-token"),
        claimed_at=_instant(),
        expires_at=_instant(minute=5),
    )
    return admission, materialization, claim


class _RecordingPublisher:
    def __init__(self) -> None:
        self.messages: list[OutboxMessage] = []

    def publish(self, message: OutboxMessage) -> None:
        self.messages.append(message)


def test_pg02_full_unit_of_work_commits_all_repository_types_atomically() -> None:
    factory = _factory()
    schedule, request, execution, attempt = _running_graph()
    admission, materialization, claim = _coordination(schedule, execution)
    message = make_outbox_message(
        event_type="execution.test",
        aggregate_type="execution",
        aggregate_id=execution.id.value,
        created_at=_instant(),
        payload={"source": "pg02"},
    )

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.executions.add(execution)
        uow.attempts.add(attempt)
        uow.admission_locks.add(admission)
        uow.materialization_leases.add(materialization)
        uow.claims.add(claim)
        uow.outbox.add(message)
        uow.commit()

    with factory() as uow:
        assert uow.schedules.get(schedule.id) is not None
        assert uow.requests.get(request.id) is not None
        assert uow.executions.get(execution.id) is not None
        assert uow.attempts.get(attempt.id) is not None
        assert uow.admission_locks.get(schedule.id) is not None
        assert uow.materialization_leases.get(schedule.id) is not None
        assert uow.claims.get(execution.id) is not None
        assert uow.outbox.get(message.id) is not None


def test_pg02_coordination_entities_round_trip_release_and_cas() -> None:
    factory = _factory()
    schedule, request, execution, attempt = _running_graph()
    admission, materialization, claim = _coordination(schedule, execution)

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.executions.add(execution)
        uow.attempts.add(attempt)
        uow.admission_locks.add(admission)
        uow.materialization_leases.add(materialization)
        uow.claims.add(claim)
        uow.commit()

    with factory() as first, factory() as second:
        first_claim = first.claims.get(execution.id)
        second_claim = second.claims.get(execution.id)
        assert first_claim is not None
        assert second_claim is not None

        assert first_claim.release(
            worker_id=first_claim.worker_id,
            token=first_claim.token,
            generation=first_claim.generation,
            released_at=_instant(minute=1),
        )
        first.claims.save(first_claim)
        first.commit()

        assert second_claim.release(
            worker_id=second_claim.worker_id,
            token=second_claim.token,
            generation=second_claim.generation,
            released_at=_instant(minute=1),
        )
        second.claims.save(second_claim)
        with pytest.raises(OptimisticConcurrencyError):
            second.commit()

    with factory() as uow:
        persisted_admission = uow.admission_locks.get(schedule.id)
        persisted_materialization = uow.materialization_leases.get(schedule.id)
        persisted_claim = uow.claims.get(execution.id)
        assert persisted_admission is not None
        assert persisted_materialization is not None
        assert persisted_claim is not None

        assert persisted_admission.release(
            worker_id=persisted_admission.worker_id,
            token=persisted_admission.token,
            generation=persisted_admission.generation,
            released_at=_instant(minute=1),
        )
        assert persisted_materialization.release(
            worker_id=persisted_materialization.worker_id,
            token=persisted_materialization.token,
            generation=persisted_materialization.generation,
            released_at=_instant(minute=1),
        )
        uow.admission_locks.save(persisted_admission)
        uow.materialization_leases.save(persisted_materialization)
        uow.commit()

    with factory() as uow:
        assert uow.admission_locks.get(schedule.id).state is ScheduleAdmissionLockState.RELEASED
        assert (
            uow.materialization_leases.get(schedule.id).state
            is ScheduleMaterializationLeaseState.RELEASED
        )
        assert uow.claims.get(execution.id).state is ExecutionClaimState.RELEASED


def test_pg02_database_unique_token_maps_to_framework_error() -> None:
    factory = _factory()
    first = _schedule("first")
    second = _schedule("second")
    shared = AdmissionToken("shared-token")

    with factory() as uow:
        uow.schedules.add(first)
        uow.schedules.add(second)
        uow.admission_locks.add(
            ScheduleAdmissionLock(
                schedule_id=first.id,
                worker_id=WorkerId("worker-a"),
                token=shared,
                acquired_at=_instant(),
                expires_at=_instant(minute=5),
            )
        )
        uow.admission_locks.add(
            ScheduleAdmissionLock(
                schedule_id=second.id,
                worker_id=WorkerId("worker-b"),
                token=shared,
                acquired_at=_instant(),
                expires_at=_instant(minute=5),
            )
        )

        with pytest.raises(DuplicateAdmissionLockError):
            uow.commit()


def test_pg02_coordination_foreign_key_maps_to_framework_error() -> None:
    factory = _factory()
    orphan = ScheduleMaterializationLease(
        schedule_id=ScheduleId("missing-schedule"),
        worker_id=WorkerId("worker-a"),
        token=MaterializationToken("orphan-token"),
        acquired_at=_instant(),
        expires_at=_instant(minute=5),
    )

    with factory() as uow:
        uow.materialization_leases.add(orphan)
        with pytest.raises(ReferentialIntegrityError):
            uow.commit()


def test_pg02_outbox_failure_remains_pending_then_publishes() -> None:
    factory = _factory()
    message = make_outbox_message(
        event_type="execution.test",
        aggregate_type="execution",
        aggregate_id="execution-1",
        created_at=_instant(),
        payload={"value": "1"},
    )

    with factory() as uow:
        uow.outbox.add(message)
        uow.commit()

    with factory() as uow:
        pending = uow.outbox.get(message.id)
        assert pending is not None
        pending.record_failure(error="broker unavailable")
        uow.outbox.save(pending)
        uow.commit()

    with factory() as uow:
        after_failure = uow.outbox.get(message.id)
        assert after_failure is not None
        assert after_failure.state is OutboxState.PENDING
        assert after_failure.publish_attempts == 1
        assert after_failure.last_error == "broker unavailable"
        assert [item.id for item in uow.outbox.list_pending(limit=10)] == [message.id]

        after_failure.mark_published(published_at=_instant(minute=2))
        uow.outbox.save(after_failure)
        uow.commit()

    with factory() as uow:
        published = uow.outbox.get(message.id)
        assert published is not None
        assert published.state is OutboxState.PUBLISHED
        assert published.publish_attempts == 2
        assert published.last_error is None
        assert uow.outbox.list_pending(limit=10) == []


def test_pg02_retention_removes_terminal_graph_and_published_outbox() -> None:
    factory = _factory()
    schedule = _schedule("retention")
    request = _request(schedule, request_id="retention-request")

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.commit()

    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(request_id=request.id, created_at=_instant())
    attempt = service.start_attempt(execution_id=execution.id, started_at=_instant())
    service.succeed_attempt(
        attempt_id=attempt.id,
        completed_at=_instant(minute=1),
    )

    publisher = _RecordingPublisher()
    dispatch = OutboxDispatcher(
        clock=FixedClock(_instant(minute=2)),
        uow_factory=factory,
        publisher=publisher,
    ).dispatch_pending()
    assert dispatch.failed == 0
    assert dispatch.published == 2

    with factory() as uow:
        uow.retention.stage_cleanup(
            executions_completed_before=_instant(hour=11),
            orphan_requests_created_before=_instant(hour=11),
            outbox_published_before=_instant(hour=11),
            limit=10,
        )
        uow.commit()
        stats = uow.retention.result

    assert stats.execution_graphs == 1
    assert stats.orphan_requests == 0
    assert stats.published_outbox_messages == 2

    with factory() as uow:
        assert uow.executions.get(execution.id) is None
        assert uow.requests.get(request.id) is None
        assert uow.attempts.get(attempt.id) is None
        assert uow.outbox.list_pending(limit=10) == []
        assert uow.schedules.get(schedule.id) is not None
