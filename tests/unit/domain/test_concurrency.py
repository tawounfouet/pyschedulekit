"""LOT-14 unit tests for concurrency admission policy."""

import pytest

from pyschedulekit.domain.concurrency import (
    ConcurrencyDecisionAction,
    ConcurrencyEvaluator,
    ConcurrencyMode,
    ConcurrencyOverflowPolicy,
    ConcurrencyPolicy,
    InvalidActiveInstanceCountError,
    InvalidConcurrencyPolicyError,
)


def test_t_con_001_allow_always_admits() -> None:
    evaluator = ConcurrencyEvaluator()
    policy = ConcurrencyPolicy.allow()

    assert policy.mode is ConcurrencyMode.ALLOW
    assert policy.max_instances is None
    assert evaluator.evaluate(policy=policy, active_instances=0).action is (
        ConcurrencyDecisionAction.ADMIT
    )
    assert evaluator.evaluate(policy=policy, active_instances=100).action is (
        ConcurrencyDecisionAction.ADMIT
    )


def test_t_con_002_limit_admits_below_capacity() -> None:
    decision = ConcurrencyEvaluator().evaluate(
        policy=ConcurrencyPolicy.limit(max_instances=2),
        active_instances=1,
    )

    assert decision.action is ConcurrencyDecisionAction.ADMIT
    assert decision.active_instances == 1
    assert decision.max_instances == 2
    assert decision.admitted


def test_t_con_003_limit_queues_at_capacity_by_default() -> None:
    decision = ConcurrencyEvaluator().evaluate(
        policy=ConcurrencyPolicy.limit(max_instances=2),
        active_instances=2,
    )

    assert decision.action is ConcurrencyDecisionAction.QUEUE
    assert not decision.admitted


def test_t_con_004_limit_can_drop_at_capacity() -> None:
    decision = ConcurrencyEvaluator().evaluate(
        policy=ConcurrencyPolicy.limit(
            max_instances=1,
            overflow=ConcurrencyOverflowPolicy.DROP,
        ),
        active_instances=1,
    )

    assert decision.action is ConcurrencyDecisionAction.DROP


def test_t_con_005_invalid_limit_is_rejected() -> None:
    with pytest.raises(InvalidConcurrencyPolicyError):
        ConcurrencyPolicy.limit(max_instances=0)

    with pytest.raises(InvalidConcurrencyPolicyError):
        ConcurrencyPolicy.limit(max_instances=-1)


def test_t_con_006_allow_cannot_define_limit() -> None:
    with pytest.raises(InvalidConcurrencyPolicyError):
        ConcurrencyPolicy(
            mode=ConcurrencyMode.ALLOW,
            max_instances=1,
        )


def test_t_con_007_negative_active_instance_count_is_rejected() -> None:
    with pytest.raises(InvalidActiveInstanceCountError):
        ConcurrencyEvaluator().evaluate(
            policy=ConcurrencyPolicy.allow(),
            active_instances=-1,
        )
