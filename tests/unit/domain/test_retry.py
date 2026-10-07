"""LOT-15 unit tests for retry policies and decisions."""

from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.execution import Failure, FailureCategory
from pyschedulekit.domain.retry import (
    ExponentialBackoff,
    FixedBackoff,
    NoBackoff,
    RetryDecisionReason,
    RetryEvaluator,
    RetryPolicy,
)
from pyschedulekit.domain.time import Duration, Instant


def _failure(
    *,
    category: FailureCategory = FailureCategory.UNKNOWN,
    retryable_hint: bool | None = None,
) -> Failure:
    return Failure(
        category=category,
        code="test.failure",
        message="boom",
        occurred_at=Instant(datetime(2026, 1, 1, tzinfo=UTC)),
        retryable_hint=retryable_hint,
    )


def test_t_retry_001_default_policy_disables_retries() -> None:
    policy = RetryPolicy()

    assert policy.max_attempts == 1
    assert policy.retries_allowed == 0
    assert isinstance(policy.backoff, NoBackoff)


def test_t_retry_002_policy_rejects_invalid_attempt_count() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        RetryPolicy(max_attempts=0)


def test_t_retry_003_fixed_backoff_is_constant() -> None:
    backoff = FixedBackoff(Duration.seconds(5))

    assert backoff.delay_for(1) == Duration.seconds(5)
    assert backoff.delay_for(4) == Duration.seconds(5)


def test_t_retry_004_exponential_backoff_grows_and_caps() -> None:
    backoff = ExponentialBackoff(
        initial_delay=Duration.seconds(2),
        multiplier=2,
        max_delay=Duration.seconds(5),
    )

    assert backoff.delay_for(1) == Duration.seconds(2)
    assert backoff.delay_for(2) == Duration.seconds(4)
    assert backoff.delay_for(3) == Duration.seconds(5)
    assert backoff.delay_for(4) == Duration.seconds(5)


def test_t_retry_005_backoff_rejects_invalid_attempt_number() -> None:
    with pytest.raises(ValueError, match="attempt_number"):
        NoBackoff().delay_for(0)


def test_t_retry_006_retryable_failure_produces_retry_decision() -> None:
    decision = RetryEvaluator().evaluate(
        policy=RetryPolicy(
            max_attempts=3,
            backoff=FixedBackoff(Duration.seconds(7)),
        ),
        attempt_number=1,
        failure=_failure(),
    )

    assert decision.should_retry is True
    assert decision.reason is RetryDecisionReason.RETRYABLE_FAILURE
    assert decision.next_attempt_number == 2
    assert decision.delay == Duration.seconds(7)


def test_t_retry_007_explicit_non_retryable_hint_stops_retry() -> None:
    decision = RetryEvaluator().evaluate(
        policy=RetryPolicy(max_attempts=5),
        attempt_number=1,
        failure=_failure(retryable_hint=False),
    )

    assert decision.should_retry is False
    assert decision.reason is RetryDecisionReason.NON_RETRYABLE_FAILURE


def test_t_retry_008_explicit_retryable_hint_overrides_category() -> None:
    decision = RetryEvaluator().evaluate(
        policy=RetryPolicy(max_attempts=2),
        attempt_number=1,
        failure=_failure(
            category=FailureCategory.PERMANENT,
            retryable_hint=True,
        ),
    )

    assert decision.should_retry is True


def test_t_retry_009_permanent_failure_is_not_retryable_by_default() -> None:
    decision = RetryEvaluator().evaluate(
        policy=RetryPolicy(max_attempts=3),
        attempt_number=1,
        failure=_failure(category=FailureCategory.PERMANENT),
    )

    assert decision.should_retry is False
    assert decision.reason is RetryDecisionReason.NON_RETRYABLE_FAILURE


def test_t_retry_010_attempt_exhaustion_stops_retry() -> None:
    decision = RetryEvaluator().evaluate(
        policy=RetryPolicy(max_attempts=3),
        attempt_number=3,
        failure=_failure(),
    )

    assert decision.should_retry is False
    assert decision.reason is RetryDecisionReason.ATTEMPTS_EXHAUSTED
