"""Retry policy foundations for logical Executions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from pyschedulekit.domain.execution import Failure, FailureCategory
from pyschedulekit.domain.time import Duration


class BackoffStrategy(Protocol):
    """Pure strategy computing delay after a failed Attempt."""

    def delay_for(self, attempt_number: int) -> Duration: ...


def _validate_attempt_number(attempt_number: int) -> None:
    if attempt_number < 1:
        raise ValueError("attempt_number must be greater than or equal to 1.")


@dataclass(frozen=True, slots=True)
class NoBackoff:
    """Retry on a later scheduler cycle without adding time delay."""

    def delay_for(self, attempt_number: int) -> Duration:
        _validate_attempt_number(attempt_number)
        return Duration.seconds(0)


@dataclass(frozen=True, slots=True)
class FixedBackoff:
    """Use one constant delay between Attempts."""

    delay: Duration

    def delay_for(self, attempt_number: int) -> Duration:
        _validate_attempt_number(attempt_number)
        return self.delay


@dataclass(frozen=True, slots=True)
class ExponentialBackoff:
    """Exponentially increase delay after each failed Attempt."""

    initial_delay: Duration
    multiplier: float = 2.0
    max_delay: Duration | None = None

    def __post_init__(self) -> None:
        if self.multiplier < 1:
            raise ValueError("multiplier must be greater than or equal to 1.")
        if self.max_delay is not None and self.max_delay < self.initial_delay:
            raise ValueError("max_delay must be greater than or equal to initial_delay.")

    def delay_for(self, attempt_number: int) -> Duration:
        _validate_attempt_number(attempt_number)
        seconds = self.initial_delay.total_seconds * self.multiplier ** (attempt_number - 1)
        delay = Duration.seconds(seconds)
        if self.max_delay is not None and delay > self.max_delay:
            return self.max_delay
        return delay


RetryBackoff = NoBackoff | FixedBackoff | ExponentialBackoff


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Declarative retry configuration snapshotted onto an Execution."""

    max_attempts: int = 1
    backoff: RetryBackoff = field(default_factory=NoBackoff)
    retryable_categories: frozenset[FailureCategory] = field(
        default_factory=lambda: frozenset(
            (
                FailureCategory.TRANSIENT,
                FailureCategory.TIMEOUT,
                FailureCategory.UNKNOWN,
            )
        )
    )

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be greater than or equal to 1.")

    @classmethod
    def none(cls) -> RetryPolicy:
        return cls(max_attempts=1)

    @property
    def retries_allowed(self) -> int:
        return self.max_attempts - 1

    def has_attempt_remaining_after(self, attempt_number: int) -> bool:
        _validate_attempt_number(attempt_number)
        return attempt_number < self.max_attempts

    def considers_retryable(self, failure: Failure) -> bool:
        if failure.retryable_hint is not None:
            return failure.retryable_hint
        return failure.category in self.retryable_categories


class RetryDecisionReason(StrEnum):
    """Reason behind one retry decision."""

    RETRYABLE_FAILURE = "retryable_failure"
    NON_RETRYABLE_FAILURE = "non_retryable_failure"
    ATTEMPTS_EXHAUSTED = "attempts_exhausted"


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """Pure decision produced after a failed Attempt."""

    should_retry: bool
    reason: RetryDecisionReason
    next_attempt_number: int | None = None
    delay: Duration | None = None

    def __post_init__(self) -> None:
        if self.should_retry:
            if self.next_attempt_number is None or self.next_attempt_number < 2:
                raise ValueError(
                    "Retry decision requires next_attempt_number greater than or equal to 2."
                )
            if self.delay is None:
                raise ValueError("Retry decision requires a delay.")
        elif self.next_attempt_number is not None or self.delay is not None:
            raise ValueError("Stop decision cannot contain retry scheduling metadata.")


class RetryEvaluator:
    """Pure domain service deciding whether one Failure should be retried."""

    def evaluate(
        self,
        *,
        policy: RetryPolicy,
        attempt_number: int,
        failure: Failure,
    ) -> RetryDecision:
        _validate_attempt_number(attempt_number)

        if not policy.considers_retryable(failure):
            return RetryDecision(
                should_retry=False,
                reason=RetryDecisionReason.NON_RETRYABLE_FAILURE,
            )

        if not policy.has_attempt_remaining_after(attempt_number):
            return RetryDecision(
                should_retry=False,
                reason=RetryDecisionReason.ATTEMPTS_EXHAUSTED,
            )

        return RetryDecision(
            should_retry=True,
            reason=RetryDecisionReason.RETRYABLE_FAILURE,
            next_attempt_number=attempt_number + 1,
            delay=policy.backoff.delay_for(attempt_number),
        )
