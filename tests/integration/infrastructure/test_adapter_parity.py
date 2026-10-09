"""Shared observable persistence contract for all qualified adapters."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest

from pyschedulekit.domain.admission_lock import AdmissionToken, ScheduleAdmissionLock
from pyschedulekit.domain.calendar import (
    CalendarRef,
    CalendarRevision,
    CalendarSnapshotRef,
)
from pyschedulekit.domain.claim import ClaimToken, ExecutionClaim, WorkerId
from pyschedulekit.domain.execution import Execution
from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.materialization_lease import (
    MaterializationToken,
    ScheduleMaterializationLease,
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
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.infrastructure.postgres import PostgresUnitOfWorkFactory
from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory
from pyschedulekit.ports.persistence import (
    DuplicateAdmissionLockError,
    DuplicateAttemptError,
    DuplicateExecutionClaimError,
    DuplicateExecutionError,
    DuplicateExecutionRequestError,
    DuplicateMaterializationLeaseError,
    DuplicateOutboxMessageError,
    DuplicateScheduleError,
    OptimisticConcurrencyError,
    ReferentialIntegrityError,
    UnitOfWorkFactory,
    UntrackedEntityError,
    UntrackedScheduleError,
)

POSTGRES_DSN = os.getenv("PYSCHEDULEKIT_TEST_POSTGRES_DSN")
ADAPTERS = ("memory", "sqlite", *(("postgres",) if POSTGRES_DSN else ()))


def _instant(*, hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _factory(adapter: str, tmp_path: Path) -> UnitOfWorkFactory:
    if adapter == "memory":
        return InMemoryUnitOfWorkFactory()
    if adapter == "sqlite":
        return SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    if adapter == "postgres":
        assert POSTGRES_DSN is not None
        return PostgresUnitOfWorkFactory(POSTGRES_DSN)
    raise AssertionError(f"Unknown adapter: {adapter}")


@pytest.fixture(autouse=True)
def _reset_postgres_adapter(adapter: str) -> Iterator[None]:
    if adapter != "postgres":
        yield
        return

    assert POSTGRES_DSN is not None
    with psycopg.connect(POSTGRES_DSN, autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")

    yield

    with psycopg.connect(POSTGRES_DSN, autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")


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
    schedule_id: ScheduleId | None = None,
    *,
    request_id: str = "request-1",
) -> ExecutionRequest:
    effective_schedule_id = schedule_id or ScheduleId("schedule-1")
    return ExecutionRequest(
        id=RequestId(request_id),
        occurrence_key=OccurrenceKey(
            schedule_id=effective_schedule_id,
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        ),
        target=TargetRef.python("jobs:refresh"),
        created_at=_instant(),
    )


def _admission_lock(schedule_id: ScheduleId) -> ScheduleAdmissionLock:
    return ScheduleAdmissionLock(
        schedule_id=schedule_id,
        worker_id=WorkerId("worker-a"),
        token=AdmissionToken("admission-token"),
        acquired_at=_instant(),
        expires_at=_instant(minute=1),
    )


def _materialization_lease(schedule_id: ScheduleId) -> ScheduleMaterializationLease:
    return ScheduleMaterializationLease(
        schedule_id=schedule_id,
        worker_id=WorkerId("worker-a"),
        token=MaterializationToken("materialization-token"),
        acquired_at=_instant(),
        expires_at=_instant(minute=1),
    )


def _claim(execution: Execution) -> ExecutionClaim:
    return ExecutionClaim(
        execution_id=execution.id,
        worker_id=WorkerId("worker-a"),
        token=ClaimToken("claim-token"),
        claimed_at=_instant(),
        expires_at=_instant(minute=1),
    )


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize(
    "orphan_kind",
    (
        "request",
        "execution",
        "attempt",
        "admission_lock",
        "materialization_lease",
        "claim",
    ),
)
def test_foreign_key_contract_rejects_orphans(
    adapter: str,
    orphan_kind: str,
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)

    with factory() as uow:
        if orphan_kind == "request":
            uow.requests.add(_request())
        elif orphan_kind in ("execution", "attempt", "claim"):
            request = _request()
            request.mark_dispatched()
            execution = Execution.from_request(
                request=request,
                created_at=_instant(),
            )
            if orphan_kind == "execution":
                uow.executions.add(execution)
            elif orphan_kind == "attempt":
                uow.attempts.add(execution.start_attempt(started_at=_instant()))
            else:
                uow.claims.add(_claim(execution))
        elif orphan_kind == "admission_lock":
            uow.admission_locks.add(_admission_lock(ScheduleId("missing-schedule")))
        elif orphan_kind == "materialization_lease":
            uow.materialization_leases.add(_materialization_lease(ScheduleId("missing-schedule")))
        else:
            raise AssertionError(f"Unknown orphan kind: {orphan_kind}")

        with pytest.raises(ReferentialIntegrityError):
            uow.commit()


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_complete_staged_graph_commits_in_one_transaction(
    adapter: str,
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)
    schedule = _schedule()
    request = _request(schedule.id)
    request.mark_dispatched()
    execution = Execution.from_request(
        request=request,
        created_at=_instant(),
    )
    attempt = execution.start_attempt(started_at=_instant())

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.executions.add(execution)
        uow.attempts.add(attempt)
        uow.admission_locks.add(_admission_lock(schedule.id))
        uow.materialization_leases.add(_materialization_lease(schedule.id))
        uow.claims.add(_claim(execution))
        uow.commit()

    with factory() as uow:
        assert uow.schedules.get(schedule.id) is not None
        assert uow.requests.get(request.id) is not None
        assert uow.executions.get(execution.id) is not None
        assert uow.attempts.get(attempt.id) is not None
        assert uow.admission_locks.get(schedule.id) is not None
        assert uow.materialization_leases.get(schedule.id) is not None
        assert uow.claims.get(execution.id) is not None


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_staged_queries_observe_uncommitted_work(
    adapter: str,
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)
    pending_request = _request(request_id="pending-request")
    execution_request = _request(
        ScheduleId("execution-schedule"),
        request_id="execution-request",
    )
    execution_request.mark_dispatched()
    execution = Execution.from_request(
        request=execution_request,
        created_at=_instant(),
    )

    with factory() as uow:
        uow.requests.add(pending_request)

        assert uow.requests.has_pending() is True
        assert [item.id for item in uow.requests.list_pending(limit=1)] == [pending_request.id]

        uow.requests.add(execution_request)
        uow.executions.add(execution)

        assert uow.executions.next_runnable_at(now=_instant()) == _instant()


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_rollback_discards_staged_state(adapter: str, tmp_path: Path) -> None:
    factory = _factory(adapter, tmp_path)
    schedule = _schedule("rollback-schedule")

    with factory() as uow:
        uow.schedules.add(schedule)

    with factory() as uow:
        assert uow.schedules.get(schedule.id) is None


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_duplicate_schedule_uses_framework_error(adapter: str, tmp_path: Path) -> None:
    factory = _factory(adapter, tmp_path)

    with factory() as uow:
        uow.schedules.add(_schedule("duplicate"))
        uow.commit()

    with factory() as uow:
        uow.schedules.add(_schedule("duplicate"))
        with pytest.raises(DuplicateScheduleError):
            uow.commit()


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_schedule_compare_and_swap_rejects_lost_update(
    adapter: str,
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)
    schedule = _schedule("cas-schedule")

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.commit()

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


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_committed_due_and_runnable_queries_share_ordering_contract(
    adapter: str,
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)
    schedule = _schedule("query-schedule")
    request = _request(schedule.id, request_id="query-request")
    request.mark_dispatched()
    execution = Execution.from_request(request=request, created_at=_instant())

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.executions.add(execution)
        uow.commit()

    with factory() as uow:
        assert uow.schedules.next_run_time() == _instant()
        assert [item.id for item in uow.schedules.list_due(now=_instant(), limit=10)] == [
            schedule.id
        ]
        assert uow.executions.next_runnable_at(now=_instant()) == _instant()
        assert [item.id for item in uow.executions.list_runnable(now=_instant(), limit=10)] == [
            execution.id
        ]


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_coordination_entities_share_release_and_cas_contract(
    adapter: str,
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)
    schedule = _schedule("coordination")
    request = _request(schedule.id, request_id="coordination-request")
    request.mark_dispatched()
    execution = Execution.from_request(request=request, created_at=_instant())
    admission = _admission_lock(schedule.id)
    materialization = _materialization_lease(schedule.id)
    claim = _claim(execution)

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.executions.add(execution)
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
            released_at=_instant(),
        )
        first.claims.save(first_claim)
        first.commit()

        assert second_claim.release(
            worker_id=second_claim.worker_id,
            token=second_claim.token,
            generation=second_claim.generation,
            released_at=_instant(),
        )
        second.claims.save(second_claim)
        with pytest.raises(OptimisticConcurrencyError):
            second.commit()

    with factory() as uow:
        loaded_admission = uow.admission_locks.get(schedule.id)
        loaded_materialization = uow.materialization_leases.get(schedule.id)
        loaded_claim = uow.claims.get(execution.id)
        assert loaded_admission is not None
        assert loaded_materialization is not None
        assert loaded_claim is not None

        assert loaded_admission.release(
            worker_id=loaded_admission.worker_id,
            token=loaded_admission.token,
            generation=loaded_admission.generation,
            released_at=_instant(),
        )
        assert loaded_materialization.release(
            worker_id=loaded_materialization.worker_id,
            token=loaded_materialization.token,
            generation=loaded_materialization.generation,
            released_at=_instant(),
        )
        uow.admission_locks.save(loaded_admission)
        uow.materialization_leases.save(loaded_materialization)
        uow.commit()

    with factory() as uow:
        assert uow.admission_locks.get(schedule.id).released_at == _instant()
        assert uow.materialization_leases.get(schedule.id).released_at == _instant()
        assert uow.claims.get(execution.id).released_at == _instant()


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_outbox_failure_and_publish_lifecycle_is_adapter_neutral(
    adapter: str,
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)
    message = OutboxMessage.create(
        event_type="execution.test",
        aggregate_type="execution",
        aggregate_id="execution-1",
        payload=(("value", "1"),),
        created_at=_instant(),
    )

    with factory() as uow:
        uow.outbox.add(message)
        uow.commit()

    with factory() as uow:
        loaded = uow.outbox.get(message.id)
        assert loaded is not None
        loaded.record_failure(error="broker unavailable")
        uow.outbox.save(loaded)
        uow.commit()

    with factory() as uow:
        failed = uow.outbox.get(message.id)
        assert failed is not None
        assert failed.state is OutboxState.PENDING
        assert failed.publish_attempts == 1
        assert failed.last_error == "broker unavailable"
        assert [item.id for item in uow.outbox.list_pending(limit=10)] == [message.id]

        failed.mark_published(published_at=_instant(minute=1))
        uow.outbox.save(failed)
        uow.commit()

    with factory() as uow:
        published = uow.outbox.get(message.id)
        assert published is not None
        assert published.state is OutboxState.PUBLISHED
        assert published.publish_attempts == 2
        assert published.last_error is None
        assert uow.outbox.list_pending(limit=10) == []


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_retention_cleanup_is_bounded_and_adapter_neutral(
    adapter: str,
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)
    schedule = _schedule("retention")
    request = _request(schedule.id, request_id="retention-request")
    request.mark_dispatched()
    execution = Execution.from_request(request=request, created_at=_instant())
    attempt = execution.start_attempt(started_at=_instant())
    attempt.succeed(completed_at=_instant(minute=1))
    execution.finish_attempt(attempt=attempt)
    message = OutboxMessage.create(
        event_type="retention.test",
        aggregate_type="execution",
        aggregate_id=execution.id.value,
        payload=(),
        created_at=_instant(),
    )
    message.mark_published(published_at=_instant(minute=1))

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.executions.add(execution)
        uow.attempts.add(attempt)
        uow.outbox.add(message)
        uow.commit()

    with factory() as uow:
        uow.retention.stage_cleanup(
            executions_completed_before=_instant(hour=11),
            orphan_requests_created_before=_instant(hour=11),
            outbox_published_before=_instant(hour=11),
            limit=10,
        )
        uow.commit()
        result = uow.retention.result

    assert result.execution_graphs == 1
    assert result.orphan_requests == 0
    assert result.published_outbox_messages == 1

    with factory() as uow:
        assert uow.schedules.get(schedule.id) is not None
        assert uow.requests.get(request.id) is None
        assert uow.executions.get(execution.id) is None
        assert uow.attempts.get(attempt.id) is None
        assert uow.outbox.get(message.id) is None


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize(
    ("entity_kind", "error_type"),
    (
        ("schedule", DuplicateScheduleError),
        ("request_id", DuplicateExecutionRequestError),
        ("request_occurrence", DuplicateExecutionRequestError),
        ("execution", DuplicateExecutionError),
        ("attempt", DuplicateAttemptError),
        ("admission_lock", DuplicateAdmissionLockError),
        ("materialization_lease", DuplicateMaterializationLeaseError),
        ("claim", DuplicateExecutionClaimError),
        ("outbox", DuplicateOutboxMessageError),
    ),
)
def test_double_staging_is_rejected_consistently(
    adapter: str,
    entity_kind: str,
    error_type: type[Exception],
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)
    schedule = _schedule("double-stage")
    request = _request(schedule.id, request_id="double-stage-request")
    request.mark_dispatched()
    execution = Execution.from_request(request=request, created_at=_instant())
    attempt = execution.start_attempt(started_at=_instant())
    admission = _admission_lock(schedule.id)
    materialization = _materialization_lease(schedule.id)
    claim = _claim(execution)
    message = OutboxMessage.create(
        event_type="double.stage",
        aggregate_type="execution",
        aggregate_id=execution.id.value,
        payload=(),
        created_at=_instant(),
    )

    with factory() as uow:
        if entity_kind == "schedule":
            uow.schedules.add(schedule)
            with pytest.raises(error_type):
                uow.schedules.add(schedule)
        elif entity_kind == "request_id":
            uow.requests.add(request)
            with pytest.raises(error_type):
                uow.requests.add(request)
        elif entity_kind == "request_occurrence":
            uow.requests.add(request)
            duplicate_occurrence = _request(
                schedule.id,
                request_id="different-request-id",
            )
            duplicate_occurrence.mark_dispatched()
            with pytest.raises(error_type):
                uow.requests.add(duplicate_occurrence)
        elif entity_kind == "execution":
            uow.executions.add(execution)
            with pytest.raises(error_type):
                uow.executions.add(execution)
        elif entity_kind == "attempt":
            uow.attempts.add(attempt)
            with pytest.raises(error_type):
                uow.attempts.add(attempt)
        elif entity_kind == "admission_lock":
            uow.admission_locks.add(admission)
            with pytest.raises(error_type):
                uow.admission_locks.add(admission)
        elif entity_kind == "materialization_lease":
            uow.materialization_leases.add(materialization)
            with pytest.raises(error_type):
                uow.materialization_leases.add(materialization)
        elif entity_kind == "claim":
            uow.claims.add(claim)
            with pytest.raises(error_type):
                uow.claims.add(claim)
        elif entity_kind == "outbox":
            uow.outbox.add(message)
            with pytest.raises(error_type):
                uow.outbox.add(message)
        else:
            raise AssertionError(f"Unknown entity kind: {entity_kind}")


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize(
    "entity_kind",
    (
        "schedule",
        "request",
        "execution",
        "attempt",
        "admission_lock",
        "materialization_lease",
        "claim",
        "outbox",
    ),
)
def test_save_requires_identity_map_tracking(
    adapter: str,
    entity_kind: str,
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)
    schedule = _schedule("untracked")
    request = _request(schedule.id, request_id="untracked-request")
    request.mark_dispatched()
    execution = Execution.from_request(request=request, created_at=_instant())
    attempt = execution.start_attempt(started_at=_instant())
    admission = _admission_lock(schedule.id)
    materialization = _materialization_lease(schedule.id)
    claim = _claim(execution)
    message = OutboxMessage.create(
        event_type="untracked.test",
        aggregate_type="execution",
        aggregate_id=execution.id.value,
        payload=(),
        created_at=_instant(),
    )

    with factory() as uow:
        if entity_kind == "schedule":
            with pytest.raises(UntrackedScheduleError):
                uow.schedules.save(schedule)
        elif entity_kind == "request":
            with pytest.raises(UntrackedEntityError):
                uow.requests.save(request)
        elif entity_kind == "execution":
            with pytest.raises(UntrackedEntityError):
                uow.executions.save(execution)
        elif entity_kind == "attempt":
            with pytest.raises(UntrackedEntityError):
                uow.attempts.save(attempt)
        elif entity_kind == "admission_lock":
            with pytest.raises(UntrackedEntityError):
                uow.admission_locks.save(admission)
        elif entity_kind == "materialization_lease":
            with pytest.raises(UntrackedEntityError):
                uow.materialization_leases.save(materialization)
        elif entity_kind == "claim":
            with pytest.raises(UntrackedEntityError):
                uow.claims.save(claim)
        elif entity_kind == "outbox":
            with pytest.raises(UntrackedEntityError):
                uow.outbox.save(message)
        else:
            raise AssertionError(f"Unknown entity kind: {entity_kind}")


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_repository_limits_and_empty_horizons_are_consistent(
    adapter: str,
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)

    with factory() as uow:
        assert uow.schedules.next_run_time() is None
        assert uow.executions.next_runnable_at(now=_instant()) is None

        with pytest.raises(ValueError):
            uow.schedules.list_due(now=_instant(), limit=0)
        with pytest.raises(ValueError):
            uow.requests.list_pending(limit=0)
        with pytest.raises(ValueError):
            uow.requests.list_admission_candidates(limit=0)
        with pytest.raises(ValueError):
            uow.requests.list_for_reconciliation(limit=0)
        with pytest.raises(ValueError):
            uow.executions.list_queued(limit=0)
        with pytest.raises(ValueError):
            uow.executions.list_runnable(now=_instant(), limit=0)
        with pytest.raises(ValueError):
            uow.executions.list_running(limit=0)
        with pytest.raises(ValueError):
            uow.executions.list_for_reconciliation(limit=0)
        with pytest.raises(ValueError):
            uow.outbox.list_pending(limit=0)
        with pytest.raises(ValueError):
            uow.retention.stage_cleanup(
                executions_completed_before=_instant(),
                orphan_requests_created_before=_instant(),
                outbox_published_before=_instant(),
                limit=0,
            )


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_identity_map_secondary_lookups_and_reconciliation_are_consistent(
    adapter: str,
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)
    schedule = _schedule("lookup")
    request = _request(schedule.id, request_id="lookup-request")
    request.mark_dispatched()
    execution = Execution.from_request(request=request, created_at=_instant())

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.executions.add(execution)
        uow.commit()

    with factory() as uow:
        first_schedule = uow.schedules.get(schedule.id)
        second_schedule = uow.schedules.get(schedule.id)
        first_request = uow.requests.get(request.id)
        second_request = uow.requests.get_by_occurrence(request.occurrence_key)
        first_execution = uow.executions.get(execution.id)
        second_execution = uow.executions.get_by_request(request.id)

        assert first_schedule is second_schedule
        assert first_request is second_request
        assert first_execution is second_execution
        assert [item.id for item in uow.requests.list_for_reconciliation(limit=10)] == [request.id]
        assert [item.id for item in uow.executions.list_for_reconciliation(limit=10)] == [
            execution.id
        ]
        assert [item.id for item in uow.executions.list_queued(limit=10)] == [execution.id]
        assert uow.executions.list_running(limit=10) == []
        assert uow.executions.count_non_terminal_for_schedule(schedule.id) == 1

        assert uow.schedules.get(ScheduleId("missing")) is None
        assert uow.requests.get(RequestId("missing")) is None
        assert uow.executions.get_by_request(RequestId("missing")) is None
        assert uow.admission_locks.get(ScheduleId("missing")) is None
        assert uow.materialization_leases.get(ScheduleId("missing")) is None


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_outbox_compare_and_swap_rejects_lost_update(
    adapter: str,
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)
    message = OutboxMessage.create(
        event_type="outbox.cas",
        aggregate_type="execution",
        aggregate_id="execution-1",
        payload=(),
        created_at=_instant(),
    )

    with factory() as uow:
        uow.outbox.add(message)
        uow.commit()

    with factory() as first, factory() as second:
        first_message = first.outbox.get(message.id)
        second_message = second.outbox.get(message.id)
        assert first_message is not None
        assert second_message is not None

        first_message.record_failure(error="first")
        first.outbox.save(first_message)
        first.commit()

        second_message.record_failure(error="second")
        second.outbox.save(second_message)
        with pytest.raises(OptimisticConcurrencyError):
            second.commit()


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_unit_of_work_requires_context_and_rejects_reentry(
    adapter: str,
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)
    uow = factory()

    with pytest.raises(RuntimeError):
        uow.commit()

    with uow, pytest.raises(RuntimeError):
        uow.__enter__()

@pytest.mark.parametrize("adapter", ADAPTERS)
def test_calendar_snapshot_binding_round_trips_across_adapters(
    adapter: str,
    tmp_path: Path,
) -> None:
    factory = _factory(adapter, tmp_path)
    calendar = CalendarSnapshotRef(
        calendar_ref=CalendarRef("market-days"),
        revision=CalendarRevision(7),
    )
    schedule = Schedule.create(
        schedule_id=ScheduleId("calendar-bound"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:calendar"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(),
            ),
            calendar=calendar,
        ),
        reference=_instant(hour=9),
    )

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.commit()

    with factory() as uow:
        loaded = uow.schedules.get(schedule.id)

    assert loaded is not None
    assert loaded.definition.calendar == calendar
    assert loaded.definition == schedule.definition

