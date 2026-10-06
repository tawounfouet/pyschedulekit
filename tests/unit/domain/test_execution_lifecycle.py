"""LOT-09 unit tests for execution lifecycle state machines."""

from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.execution import (
    AttemptState,
    Execution,
    ExecutionPolicySnapshot,
    ExecutionState,
    Failure,
    FailureCategory,
    InvalidAttemptTransitionError,
    InvalidExecutionTransitionError,
)
from pyschedulekit.domain.execution_request import (
    ExecutionRequest,
    ExecutionRequestState,
    InvalidExecutionRequestTransitionError,
    RequestId,
)
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.schedule import ScheduleId, ScheduleRevision, TargetRef
from pyschedulekit.domain.time import Duration, Instant


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _request() -> ExecutionRequest:
    return ExecutionRequest(
        id=RequestId("request-1"),
        occurrence_key=OccurrenceKey(
            schedule_id=ScheduleId("schedule-1"),
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        ),
        target=TargetRef.python("app.tasks:refresh"),
        created_at=_instant(hour=9, minute=59),
    )


def _dispatched_request() -> ExecutionRequest:
    request = _request()
    request.mark_dispatched()
    return request


def _execution() -> Execution:
    return Execution.from_request(
        request=_dispatched_request(),
        created_at=_instant(),
        policy_snapshot=ExecutionPolicySnapshot(timeout=Duration.minutes(5)),
    )


def _failure(at: Instant | None = None) -> Failure:
    return Failure(
        category=FailureCategory.TRANSIENT,
        code="target.unavailable",
        message="Target is temporarily unavailable.",
        occurred_at=at or _instant(hour=10, minute=1),
        retryable_hint=True,
    )


def test_t_exe_001_request_starts_pending() -> None:
    request = _request()

    assert request.state is ExecutionRequestState.PENDING
    assert request.version == 0


def test_t_exe_002_request_can_wait_for_admission_then_dispatch() -> None:
    request = _request()

    request.wait_for_admission()
    assert request.state is ExecutionRequestState.WAITING_ADMISSION
    assert request.version == 1

    request.mark_dispatched()
    assert request.state is ExecutionRequestState.DISPATCHED
    assert request.version == 2


def test_t_exe_003_cancelled_request_cannot_be_dispatched() -> None:
    request = _request()
    request.cancel()

    with pytest.raises(InvalidExecutionRequestTransitionError):
        request.mark_dispatched()


def test_request_terminal_transition_is_idempotent_only_for_same_state() -> None:
    request = _request()
    request.cancel()
    version = request.version

    request.cancel()

    assert request.version == version

    with pytest.raises(InvalidExecutionRequestTransitionError):
        request.wait_for_admission()


def test_t_exe_004_execution_starts_queued() -> None:
    execution = _execution()

    assert execution.state is ExecutionState.QUEUED
    assert execution.attempt_count == 0
    assert execution.active_attempt_number is None
    assert execution.result is None


def test_execution_requires_dispatched_request() -> None:
    request = _request()

    with pytest.raises(InvalidExecutionTransitionError):
        Execution.from_request(request=request, created_at=_instant())


def test_t_exe_005_start_attempt_moves_execution_to_running() -> None:
    execution = _execution()

    attempt = execution.start_attempt(started_at=_instant(hour=10, minute=1))

    assert execution.state is ExecutionState.RUNNING
    assert execution.attempt_count == 1
    assert execution.active_attempt_number == 1
    assert attempt.state is AttemptState.RUNNING
    assert attempt.number == 1
    assert attempt.execution_id == execution.id


def test_t_exe_006_execution_allows_only_one_active_attempt() -> None:
    execution = _execution()
    execution.start_attempt(started_at=_instant(hour=10, minute=1))

    with pytest.raises(InvalidExecutionTransitionError, match="state"):
        execution.start_attempt(started_at=_instant(hour=10, minute=2))


def test_t_exe_007_successful_attempt_completes_execution() -> None:
    execution = _execution()
    attempt = execution.start_attempt(started_at=_instant(hour=10, minute=1))

    attempt.succeed(completed_at=_instant(hour=10, minute=2))
    result = execution.finish_attempt(attempt=attempt)

    assert result is not None
    assert result.state is ExecutionState.SUCCESS
    assert result.failure is None
    assert execution.state is ExecutionState.SUCCESS
    assert execution.result == result
    assert execution.active_attempt_number is None


def test_t_exe_008_failed_attempt_without_retry_fails_execution() -> None:
    execution = _execution()
    attempt = execution.start_attempt(started_at=_instant(hour=10, minute=1))
    failure = _failure()

    attempt.fail(failure=failure, completed_at=_instant(hour=10, minute=2))
    result = execution.finish_attempt(attempt=attempt)

    assert result is not None
    assert result.state is ExecutionState.FAILED
    assert result.failure == failure
    assert execution.state is ExecutionState.FAILED


def test_t_exe_009_retry_wait_keeps_same_execution_and_creates_new_attempt_number() -> None:
    execution = _execution()
    execution_id = execution.id
    idempotency_key = execution.idempotency_key
    first = execution.start_attempt(started_at=_instant(hour=10, minute=1))

    first.fail(failure=_failure(), completed_at=_instant(hour=10, minute=2))
    result = execution.finish_attempt(
        attempt=first,
        retry_at=_instant(hour=10, minute=5),
    )

    assert result is None
    assert execution.state is ExecutionState.RETRY_WAIT
    assert execution.next_attempt_at == _instant(hour=10, minute=5)
    assert execution.id == execution_id
    assert execution.idempotency_key == idempotency_key

    second = execution.start_attempt(started_at=_instant(hour=10, minute=5))

    assert second.number == 2
    assert second.id != first.id
    assert execution.id == execution_id
    assert execution.idempotency_key == idempotency_key


def test_retry_attempt_cannot_start_before_retry_at() -> None:
    execution = _execution()
    first = execution.start_attempt(started_at=_instant(hour=10, minute=1))
    first.fail(failure=_failure(), completed_at=_instant(hour=10, minute=2))
    execution.finish_attempt(
        attempt=first,
        retry_at=_instant(hour=10, minute=5),
    )

    with pytest.raises(InvalidExecutionTransitionError, match="before next_attempt_at"):
        execution.start_attempt(started_at=_instant(hour=10, minute=4))


def test_t_exe_010_timeout_is_a_terminal_outcome_without_retry_decision() -> None:
    execution = _execution()
    attempt = execution.start_attempt(started_at=_instant(hour=10, minute=1))

    attempt.timeout(completed_at=_instant(hour=10, minute=6))
    result = execution.finish_attempt(attempt=attempt)

    assert result is not None
    assert result.state is ExecutionState.TIMED_OUT
    assert result.failure is not None
    assert result.failure.category is FailureCategory.TIMEOUT


def test_t_exe_011_queued_execution_can_be_cancelled_without_attempt() -> None:
    execution = _execution()

    result = execution.cancel(completed_at=_instant(hour=10, minute=1))

    assert result.state is ExecutionState.CANCELLED
    assert execution.state is ExecutionState.CANCELLED
    assert execution.attempt_count == 0


def test_running_execution_must_cancel_through_active_attempt() -> None:
    execution = _execution()
    attempt = execution.start_attempt(started_at=_instant(hour=10, minute=1))

    with pytest.raises(InvalidExecutionTransitionError):
        execution.cancel(completed_at=_instant(hour=10, minute=2))

    attempt.cancel(completed_at=_instant(hour=10, minute=2))
    result = execution.finish_attempt(attempt=attempt)

    assert result is not None
    assert result.state is ExecutionState.CANCELLED


def test_t_exe_012_attempt_cannot_complete_twice() -> None:
    execution = _execution()
    attempt = execution.start_attempt(started_at=_instant(hour=10, minute=1))
    attempt.succeed(completed_at=_instant(hour=10, minute=2))

    with pytest.raises(InvalidAttemptTransitionError):
        attempt.succeed(completed_at=_instant(hour=10, minute=3))


def test_attempt_from_other_execution_cannot_complete_execution() -> None:
    execution = _execution()
    active = execution.start_attempt(started_at=_instant(hour=10, minute=1))

    other = _execution()
    other_attempt = other.start_attempt(started_at=_instant(hour=10, minute=1))
    other_attempt.succeed(completed_at=_instant(hour=10, minute=2))

    assert active.id == other_attempt.id

    with pytest.raises(InvalidExecutionTransitionError):
        execution.finish_attempt(attempt=other_attempt)


def test_execution_policy_snapshot_is_frozen_at_creation() -> None:
    timeout = Duration.minutes(5)
    execution = _execution()

    assert execution.policy_snapshot == ExecutionPolicySnapshot(timeout=timeout)
