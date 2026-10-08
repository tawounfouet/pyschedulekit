"""LOT-17 unit tests for execution cancellation semantics."""

from datetime import UTC, datetime

from pyschedulekit.domain.execution import (
    Execution,
    ExecutionId,
    ExecutionPolicySnapshot,
    ExecutionState,
    Failure,
    FailureCategory,
    IdempotencyKey,
)
from pyschedulekit.domain.execution_request import RequestId
from pyschedulekit.domain.schedule import TargetRef
from pyschedulekit.domain.time import Instant


def _instant(second: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, second, tzinfo=UTC))


def _execution() -> Execution:
    return Execution(
        execution_id=ExecutionId("execution-cancel"),
        request_id=RequestId("request-cancel"),
        target=TargetRef.python("job"),
        created_at=_instant(),
        policy_snapshot=ExecutionPolicySnapshot(),
        idempotency_key=IdempotencyKey("idem-cancel"),
    )


def test_t_cancel_001_queued_execution_cancels_immediately() -> None:
    execution = _execution()

    result = execution.cancel(completed_at=_instant(1))

    assert execution.state is ExecutionState.CANCELLED
    assert execution.cancellation_requested
    assert execution.cancellation_requested_at == _instant(1)
    assert result.state is ExecutionState.CANCELLED


def test_t_cancel_002_running_execution_records_cancellation_request() -> None:
    execution = _execution()
    execution.start_attempt(started_at=_instant())

    changed = execution.request_cancellation(requested_at=_instant(1))

    assert changed is True
    assert execution.state is ExecutionState.RUNNING
    assert execution.cancellation_requested_at == _instant(1)


def test_t_cancel_003_repeated_running_cancellation_request_is_idempotent() -> None:
    execution = _execution()
    execution.start_attempt(started_at=_instant())

    assert execution.request_cancellation(requested_at=_instant(1)) is True
    version = execution.version
    assert execution.request_cancellation(requested_at=_instant(2)) is False
    assert execution.version == version
    assert execution.cancellation_requested_at == _instant(1)


def _failure() -> Failure:
    return Failure(
        category=FailureCategory.TRANSIENT,
        code="target.unavailable",
        message="Target is temporarily unavailable.",
        occurred_at=_instant(2),
        retryable_hint=True,
    )


def test_t_cancel_004_requested_cancellation_prevents_retry_wait_on_failure() -> None:
    execution = _execution()
    attempt = execution.start_attempt(started_at=_instant())
    execution.request_cancellation(requested_at=_instant(1))
    attempt.fail(failure=_failure(), completed_at=_instant(2))

    result = execution.finish_attempt(attempt=attempt, retry_at=_instant(10))

    assert result is not None
    assert execution.state is ExecutionState.FAILED
    assert execution.state is not ExecutionState.RETRY_WAIT
    assert execution.next_attempt_at is None


def test_t_cancel_005_requested_cancellation_prevents_retry_wait_on_timeout() -> None:
    execution = _execution()
    attempt = execution.start_attempt(started_at=_instant())
    execution.request_cancellation(requested_at=_instant(1))
    attempt.timeout(completed_at=_instant(2))

    result = execution.finish_attempt(attempt=attempt, retry_at=_instant(10))

    assert result is not None
    assert execution.state is ExecutionState.TIMED_OUT
    assert execution.state is not ExecutionState.RETRY_WAIT
    assert execution.next_attempt_at is None
