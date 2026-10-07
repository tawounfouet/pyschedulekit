"""Concurrency admission policy and pure decision model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class InvalidConcurrencyPolicyError(ValueError):
    """Raised when a ConcurrencyPolicy violates its invariants."""


class InvalidActiveInstanceCountError(ValueError):
    """Raised when an evaluator receives an impossible active count."""


class ConcurrencyMode(StrEnum):
    """High-level concurrency strategy."""

    ALLOW = "allow"
    LIMIT = "limit"


class ConcurrencyOverflowPolicy(StrEnum):
    """Behavior when a concurrency limit has no free slot."""

    QUEUE = "queue"
    DROP = "drop"


class ConcurrencyDecisionAction(StrEnum):
    """Concrete admission decision for one ExecutionRequest."""

    ADMIT = "admit"
    QUEUE = "queue"
    DROP = "drop"


@dataclass(frozen=True, slots=True)
class ConcurrencyPolicy:
    """Immutable per-Schedule concurrency policy."""

    mode: ConcurrencyMode = ConcurrencyMode.ALLOW
    max_instances: int | None = None
    overflow: ConcurrencyOverflowPolicy = ConcurrencyOverflowPolicy.QUEUE

    def __post_init__(self) -> None:
        if self.mode is ConcurrencyMode.ALLOW:
            if self.max_instances is not None:
                raise InvalidConcurrencyPolicyError(
                    "ALLOW concurrency policy must not define max_instances."
                )
            return

        if self.max_instances is None or self.max_instances < 1:
            raise InvalidConcurrencyPolicyError(
                "LIMIT concurrency policy requires max_instances >= 1."
            )

    @classmethod
    def allow(cls) -> ConcurrencyPolicy:
        return cls(mode=ConcurrencyMode.ALLOW)

    @classmethod
    def limit(
        cls,
        *,
        max_instances: int,
        overflow: ConcurrencyOverflowPolicy = ConcurrencyOverflowPolicy.QUEUE,
    ) -> ConcurrencyPolicy:
        return cls(
            mode=ConcurrencyMode.LIMIT,
            max_instances=max_instances,
            overflow=overflow,
        )


@dataclass(frozen=True, slots=True)
class ConcurrencyDecision:
    """Pure admission result from policy plus current slot usage."""

    action: ConcurrencyDecisionAction
    active_instances: int
    max_instances: int | None

    @property
    def admitted(self) -> bool:
        return self.action is ConcurrencyDecisionAction.ADMIT


class ConcurrencyEvaluator:
    """Answer SHOULD this request be admitted given current slot usage?"""

    def evaluate(
        self,
        *,
        policy: ConcurrencyPolicy,
        active_instances: int,
    ) -> ConcurrencyDecision:
        if active_instances < 0:
            raise InvalidActiveInstanceCountError(
                "active_instances must be greater than or equal to 0."
            )

        if policy.mode is ConcurrencyMode.ALLOW:
            return ConcurrencyDecision(
                action=ConcurrencyDecisionAction.ADMIT,
                active_instances=active_instances,
                max_instances=None,
            )

        assert policy.max_instances is not None
        if active_instances < policy.max_instances:
            action = ConcurrencyDecisionAction.ADMIT
        elif policy.overflow is ConcurrencyOverflowPolicy.QUEUE:
            action = ConcurrencyDecisionAction.QUEUE
        else:
            action = ConcurrencyDecisionAction.DROP

        return ConcurrencyDecision(
            action=action,
            active_instances=active_instances,
            max_instances=policy.max_instances,
        )
