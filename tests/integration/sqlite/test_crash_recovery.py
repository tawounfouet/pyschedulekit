"""LOT-23 integration tests for persisted crash recovery."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from pyschedulekit import (
    CrashRecoveryIncompleteError,
    Duration,
    FixedBackoff,
    RetryPolicy,
    Scheduler,
)
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.application.recovery import CrashRecoveryService
from pyschedulekit.domain.execution import AttemptState, ExecutionState
from pyschedulekit.domain.execution_request import ExecutionRequest
from pyschedulekit.domain.occurrence import Occurrence
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleRevision,
    TargetRef,
)
from pyschedulekit.domain.time import Instant
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _seed_running_execution(
    factory: SqliteUnitOfWorkFactory,
    *,
    retry: RetryPolicy,
):
    schedule = Schedule.create(
        schedule_id=ScheduleId("crash-schedule"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:crash"),
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
    attempt = service.start_attempt(
        execution_id=execution.id,
        started_at=_instant(),
    )
    return service, execution, attempt


def test_t_recovery_001_orphaned_running_attempt_is_retried(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    retry = RetryPolicy(
        max_attempts=3,
        backoff=FixedBackoff(Duration.minutes(5)),
    )
    _, execution, attempt = _seed_running_execution(factory, retry=retry)
    clock = MutableClock(_instant(minute=1))

    result = CrashRecoveryService(
        clock=clock,
        uow_factory=factory,
    ).recover()

    assert result.complete is True
    assert result.retried_execution_ids == (execution.id,)
    assert result.failed_execution_ids == ()
    assert result.errors == ()

    with factory() as uow:
        recovered_execution = uow.executions.get(execution.id)
        recovered_attempt = uow.attempts.get(attempt.id)

        assert recovered_execution is not None
        assert recovered_attempt is not None
        assert recovered_execution.state is ExecutionState.RETRY_WAIT
        assert recovered_execution.next_attempt_at == _instant(minute=6)
        assert recovered_attempt.state is AttemptState.FAILED
        assert recovered_attempt.result is not None
        assert recovered_attempt.result.failure is not None
        assert recovered_attempt.result.failure.code == "execution.crash_recovered"


def test_t_recovery_002_exhausted_execution_fails_terminally(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    _, execution, attempt = _seed_running_execution(
        factory,
        retry=RetryPolicy.none(),
    )

    result = CrashRecoveryService(
        clock=MutableClock(_instant(minute=1)),
        uow_factory=factory,
    ).recover()

    assert result.complete is True
    assert result.failed_execution_ids == (execution.id,)

    with factory() as uow:
        recovered_execution = uow.executions.get(execution.id)
        recovered_attempt = uow.attempts.get(attempt.id)

        assert recovered_execution is not None
        assert recovered_attempt is not None
        assert recovered_execution.state is ExecutionState.FAILED
        assert recovered_execution.result is not None
        assert recovered_execution.result.failure is not None
        assert recovered_execution.result.failure.code == "execution.crash_recovered"
        assert recovered_attempt.state is AttemptState.FAILED


def test_t_recovery_003_pending_cancellation_wins_over_retry(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    service, execution, attempt = _seed_running_execution(
        factory,
        retry=RetryPolicy(max_attempts=3),
    )
    service.request_cancellation(
        execution_id=execution.id,
        requested_at=_instant(minute=1),
    )

    result = CrashRecoveryService(
        clock=MutableClock(_instant(minute=2)),
        uow_factory=factory,
    ).recover()

    assert result.complete is True
    assert result.cancelled_execution_ids == (execution.id,)
    assert result.retried_execution_ids == ()

    with factory() as uow:
        recovered_execution = uow.executions.get(execution.id)
        recovered_attempt = uow.attempts.get(attempt.id)

        assert recovered_execution is not None
        assert recovered_attempt is not None
        assert recovered_execution.state is ExecutionState.CANCELLED
        assert recovered_attempt.state is AttemptState.CANCELLED


def test_t_recovery_004_second_pass_is_idempotent(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    _, execution, _ = _seed_running_execution(
        factory,
        retry=RetryPolicy.none(),
    )
    service = CrashRecoveryService(
        clock=MutableClock(_instant(minute=1)),
        uow_factory=factory,
    )

    first = service.recover()
    second = service.recover()

    assert first.failed_execution_ids == (execution.id,)
    assert second.recovered == 0
    assert second.complete is True
    assert second.remaining_running_execution_ids == ()


def test_t_recovery_005_scheduler_blocks_on_inconsistent_running_state(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)
    _, execution, attempt = _seed_running_execution(
        factory,
        retry=RetryPolicy(max_attempts=2),
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

    scheduler = Scheduler(
        clock=MutableClock(_instant(minute=1)),
        uow_factory=factory,
    )

    with pytest.raises(CrashRecoveryIncompleteError) as captured:
        scheduler.run_pending()

    result = captured.value.result
    assert result.complete is False
    assert result.remaining_running_execution_ids == (execution.id,)
    assert len(result.errors) == 1
    assert result.errors[0].code == "recovery.missing_attempt"
    assert scheduler.last_recovery_result == result


def test_t_recovery_006_first_scheduler_cycle_recovers_before_scheduling(tmp_path) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    _, execution, _ = _seed_running_execution(
        factory,
        retry=RetryPolicy.none(),
    )
    scheduler = Scheduler(
        clock=MutableClock(_instant(minute=1)),
        uow_factory=factory,
    )

    scheduler.run_pending()

    assert scheduler.last_recovery_result is not None
    assert scheduler.last_recovery_result.complete is True
    assert scheduler.last_recovery_result.failed_execution_ids == (execution.id,)

    with factory() as uow:
        recovered = uow.executions.get(execution.id)
        assert recovered is not None
        assert recovered.state is ExecutionState.FAILED


def test_t_recovery_007_custom_retry_policy_may_reject_unknown_crash_failure(
    tmp_path,
) -> None:
    factory = SqliteUnitOfWorkFactory(tmp_path / "scheduler.db")
    retry = RetryPolicy(
        max_attempts=3,
        retryable_categories=frozenset(("transient",)),
    )
    _, execution, _ = _seed_running_execution(factory, retry=retry)

    result = CrashRecoveryService(
        clock=MutableClock(_instant(minute=1)),
        uow_factory=factory,
    ).recover()

    assert result.complete is True
    assert result.retried_execution_ids == ()
    assert result.failed_execution_ids == (execution.id,)

    with factory() as uow:
        recovered = uow.executions.get(execution.id)
        assert recovered is not None
        assert recovered.state is ExecutionState.FAILED
