"""Misfire classification and recovery-policy foundations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from pyschedulekit.domain.time import Duration, GracePeriod, Instant


class OccurrenceNotDueError(ValueError):
    """Raised when lateness is evaluated before an occurrence is due."""


class LatenessStatus(StrEnum):
    """Temporal classification of one due occurrence."""

    ON_TIME = "on_time"
    LATE_ELIGIBLE = "late_eligible"
    MISFIRED = "misfired"


class MisfirePolicyAction(StrEnum):
    """Configured recovery behavior for a truly misfired occurrence."""

    SKIP = "skip"
    RUN_NOW = "run_now"
    CATCH_UP = "catch_up"
    COALESCE = "coalesce"


class MisfireDecisionAction(StrEnum):
    """Concrete scheduling action produced by policy evaluation."""

    MATERIALIZE = "materialize"
    SKIP = "skip"
    CATCH_UP = "catch_up"
    COALESCE = "coalesce"


@dataclass(frozen=True, slots=True)
class MisfirePolicy:
    """Immutable recovery policy plus lateness grace period."""

    action: MisfirePolicyAction = MisfirePolicyAction.RUN_NOW
    grace: GracePeriod = field(default_factory=GracePeriod.zero)

    @classmethod
    def skip(cls, *, grace: GracePeriod | None = None) -> MisfirePolicy:
        return cls(
            action=MisfirePolicyAction.SKIP,
            grace=grace or GracePeriod.zero(),
        )

    @classmethod
    def run_now(cls, *, grace: GracePeriod | None = None) -> MisfirePolicy:
        return cls(
            action=MisfirePolicyAction.RUN_NOW,
            grace=grace or GracePeriod.zero(),
        )

    @classmethod
    def catch_up(cls, *, grace: GracePeriod | None = None) -> MisfirePolicy:
        return cls(
            action=MisfirePolicyAction.CATCH_UP,
            grace=grace or GracePeriod.zero(),
        )

    @classmethod
    def coalesce(cls, *, grace: GracePeriod | None = None) -> MisfirePolicy:
        return cls(
            action=MisfirePolicyAction.COALESCE,
            grace=grace or GracePeriod.zero(),
        )


@dataclass(frozen=True, slots=True)
class LatenessClassification:
    """Pure temporal classification of one scheduled occurrence."""

    scheduled_at: Instant
    evaluated_at: Instant
    lateness: Duration
    deadline: Instant
    status: LatenessStatus


@dataclass(frozen=True, slots=True)
class MisfireDecision:
    """Pure decision combining temporal classification with policy."""

    classification: LatenessClassification
    action: MisfireDecisionAction
    configured_action: MisfirePolicyAction

    @property
    def is_misfire(self) -> bool:
        return self.classification.status is LatenessStatus.MISFIRED


class LatenessClassifier:
    """Classify a due occurrence without deciding recovery behavior."""

    def classify(
        self,
        *,
        scheduled_at: Instant,
        evaluated_at: Instant,
        grace: GracePeriod,
    ) -> LatenessClassification:
        if evaluated_at < scheduled_at:
            raise OccurrenceNotDueError(
                "Cannot classify lateness before the occurrence is scheduled."
            )

        lateness = evaluated_at.elapsed_since(scheduled_at)
        deadline = grace.deadline_for(scheduled_at)

        if evaluated_at == scheduled_at:
            status = LatenessStatus.ON_TIME
        elif evaluated_at <= deadline:
            status = LatenessStatus.LATE_ELIGIBLE
        else:
            status = LatenessStatus.MISFIRED

        return LatenessClassification(
            scheduled_at=scheduled_at,
            evaluated_at=evaluated_at,
            lateness=lateness,
            deadline=deadline,
            status=status,
        )


class MisfireEvaluator:
    """Apply MisfirePolicy only after lateness has been classified."""

    def __init__(
        self,
        *,
        classifier: LatenessClassifier | None = None,
    ) -> None:
        self._classifier = classifier or LatenessClassifier()

    def evaluate(
        self,
        *,
        scheduled_at: Instant,
        evaluated_at: Instant,
        policy: MisfirePolicy,
    ) -> MisfireDecision:
        classification = self._classifier.classify(
            scheduled_at=scheduled_at,
            evaluated_at=evaluated_at,
            grace=policy.grace,
        )

        if classification.status is not LatenessStatus.MISFIRED:
            action = MisfireDecisionAction.MATERIALIZE
        elif policy.action is MisfirePolicyAction.SKIP:
            action = MisfireDecisionAction.SKIP
        elif policy.action is MisfirePolicyAction.RUN_NOW:
            action = MisfireDecisionAction.MATERIALIZE
        elif policy.action is MisfirePolicyAction.CATCH_UP:
            action = MisfireDecisionAction.CATCH_UP
        else:
            action = MisfireDecisionAction.COALESCE

        return MisfireDecision(
            classification=classification,
            action=action,
            configured_action=policy.action,
        )
