"""LOT-12 unit tests for lateness classification and MisfirePolicy."""

from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.misfire import (
    LatenessClassifier,
    LatenessStatus,
    InvalidRecoveryLimitError,
    MisfireDecisionAction,
    MisfireEvaluator,
    MisfirePolicy,
    MisfirePolicyAction,
    OccurrenceNotDueError,
)
from pyschedulekit.domain.time import Duration, GracePeriod, Instant


def _instant(minute: int = 0, second: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, minute, second, tzinfo=UTC))


def test_t_mis_001_exact_scheduled_time_is_on_time() -> None:
    classification = LatenessClassifier().classify(
        scheduled_at=_instant(),
        evaluated_at=_instant(),
        grace=GracePeriod.seconds(60),
    )

    assert classification.status is LatenessStatus.ON_TIME
    assert classification.lateness == Duration.seconds(0)
    assert classification.deadline == _instant(minute=1)


def test_t_mis_002_positive_lateness_inside_grace_is_late_eligible() -> None:
    classification = LatenessClassifier().classify(
        scheduled_at=_instant(),
        evaluated_at=_instant(second=30),
        grace=GracePeriod.seconds(60),
    )

    assert classification.status is LatenessStatus.LATE_ELIGIBLE
    assert classification.lateness == Duration.seconds(30)


def test_t_mis_003_deadline_boundary_remains_late_eligible() -> None:
    classification = LatenessClassifier().classify(
        scheduled_at=_instant(),
        evaluated_at=_instant(minute=1),
        grace=GracePeriod.seconds(60),
    )

    assert classification.status is LatenessStatus.LATE_ELIGIBLE


def test_t_mis_004_after_deadline_is_misfired() -> None:
    classification = LatenessClassifier().classify(
        scheduled_at=_instant(),
        evaluated_at=_instant(minute=1, second=1),
        grace=GracePeriod.seconds(60),
    )

    assert classification.status is LatenessStatus.MISFIRED
    assert classification.lateness == Duration.seconds(61)


def test_t_mis_005_occurrence_not_due_cannot_be_classified_as_late() -> None:
    with pytest.raises(OccurrenceNotDueError):
        LatenessClassifier().classify(
            scheduled_at=_instant(minute=1),
            evaluated_at=_instant(),
            grace=GracePeriod.seconds(60),
        )


def test_t_mis_006_skip_policy_does_not_skip_on_time_occurrence() -> None:
    decision = MisfireEvaluator().evaluate(
        scheduled_at=_instant(),
        evaluated_at=_instant(),
        policy=MisfirePolicy.skip(),
    )

    assert decision.action is MisfireDecisionAction.MATERIALIZE
    assert not decision.is_misfire


def test_t_mis_007_skip_policy_does_not_skip_late_eligible_occurrence() -> None:
    decision = MisfireEvaluator().evaluate(
        scheduled_at=_instant(),
        evaluated_at=_instant(second=30),
        policy=MisfirePolicy.skip(grace=GracePeriod.seconds(60)),
    )

    assert decision.action is MisfireDecisionAction.MATERIALIZE
    assert decision.classification.status is LatenessStatus.LATE_ELIGIBLE


def test_t_mis_008_skip_policy_skips_true_misfire() -> None:
    decision = MisfireEvaluator().evaluate(
        scheduled_at=_instant(),
        evaluated_at=_instant(minute=2),
        policy=MisfirePolicy.skip(grace=GracePeriod.seconds(60)),
    )

    assert decision.action is MisfireDecisionAction.SKIP
    assert decision.is_misfire
    assert decision.configured_action is MisfirePolicyAction.SKIP


def test_t_mis_009_run_now_materializes_true_misfire() -> None:
    decision = MisfireEvaluator().evaluate(
        scheduled_at=_instant(),
        evaluated_at=_instant(minute=2),
        policy=MisfirePolicy.run_now(grace=GracePeriod.seconds(60)),
    )

    assert decision.action is MisfireDecisionAction.MATERIALIZE
    assert decision.is_misfire
    assert decision.configured_action is MisfirePolicyAction.RUN_NOW


def test_t_mis_010_catch_up_is_modeled_as_distinct_recovery_decision() -> None:
    decision = MisfireEvaluator().evaluate(
        scheduled_at=_instant(),
        evaluated_at=_instant(minute=2),
        policy=MisfirePolicy.catch_up(grace=GracePeriod.seconds(60)),
    )

    assert decision.action is MisfireDecisionAction.CATCH_UP
    assert decision.configured_action is MisfirePolicyAction.CATCH_UP


def test_t_mis_011_coalesce_is_modeled_as_distinct_recovery_decision() -> None:
    decision = MisfireEvaluator().evaluate(
        scheduled_at=_instant(),
        evaluated_at=_instant(minute=2),
        policy=MisfirePolicy.coalesce(grace=GracePeriod.seconds(60)),
    )

    assert decision.action is MisfireDecisionAction.COALESCE
    assert decision.configured_action is MisfirePolicyAction.COALESCE


def test_t_mis_012_policy_factories_preserve_explicit_grace() -> None:
    grace = GracePeriod.seconds(90)

    assert MisfirePolicy.skip(grace=grace).grace == grace
    assert MisfirePolicy.run_now(grace=grace).grace == grace
    assert MisfirePolicy.catch_up(grace=grace).grace == grace
    assert MisfirePolicy.coalesce(grace=grace).grace == grace


def test_t_mis_013_recovery_limit_must_be_positive() -> None:
    with pytest.raises(InvalidRecoveryLimitError):
        MisfirePolicy.catch_up(max_occurrences=0)

    with pytest.raises(InvalidRecoveryLimitError):
        MisfirePolicy.coalesce(max_occurrences=-1)


def test_t_mis_014_policy_factories_preserve_recovery_limit() -> None:
    assert MisfirePolicy.catch_up(max_occurrences=7).max_occurrences == 7
    assert MisfirePolicy.coalesce(max_occurrences=11).max_occurrences == 11
