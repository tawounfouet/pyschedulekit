"""LOT-33 unit tests for target-kind executor routing."""

from dataclasses import dataclass

import pytest

from pyschedulekit.domain.schedule import TargetRef
from pyschedulekit.domain.time import Duration
from pyschedulekit.infrastructure.routing_executor import RoutingExecutor
from pyschedulekit.ports.cancellation import CancellationToken
from pyschedulekit.ports.executor import (
    ExecutorOutcome,
    PreparedTarget,
    TargetResolutionError,
    UnsupportedTargetError,
)


@dataclass(frozen=True, slots=True)
class _Prepared:
    target: TargetRef


class _Executor:
    def __init__(self) -> None:
        self.executed: list[tuple[int | None, str | None]] = []

    def prepare(self, target: TargetRef) -> PreparedTarget:
        return _Prepared(target)

    def execute(
        self,
        prepared: PreparedTarget,
        *,
        timeout: Duration | None = None,
        cancellation_token: CancellationToken | None = None,
        fencing_token: int | None = None,
        idempotency_key: str | None = None,
    ) -> ExecutorOutcome:
        del prepared, timeout, cancellation_token
        self.executed.append((fencing_token, idempotency_key))
        return ExecutorOutcome()


class _BadExecutor(_Executor):
    def prepare(self, target: TargetRef) -> PreparedTarget:
        del target
        return _Prepared(TargetRef.python("different"))


def test_t_executor_router_001_routes_by_target_kind() -> None:
    python_executor = _Executor()
    http_executor = _Executor()
    router = RoutingExecutor(
        {
            "python": python_executor,
            "http": http_executor,
        }
    )

    prepared = router.prepare(TargetRef.http("notify"))
    outcome = router.execute(
        prepared,
        fencing_token=7,
        idempotency_key="idem-1",
    )

    assert outcome.succeeded
    assert python_executor.executed == []
    assert http_executor.executed == [(7, "idem-1")]
    assert router.target_kinds == ("http", "python")


def test_t_executor_router_002_unknown_kind_fails_before_attempt_execution() -> None:
    router = RoutingExecutor({"python": _Executor()})

    with pytest.raises(UnsupportedTargetError, match="workflow"):
        router.prepare(TargetRef.workflow("workflow-1"))


def test_t_executor_router_003_rejects_executor_that_changes_target_identity() -> None:
    router = RoutingExecutor({"http": _BadExecutor()})

    with pytest.raises(TargetResolutionError, match="different"):
        router.prepare(TargetRef.http("notify"))


def test_t_executor_router_004_requires_at_least_one_executor() -> None:
    with pytest.raises(ValueError, match="at least one"):
        RoutingExecutor({})
