"""Unit tests for the instance-owned ExecutorRegistry."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from pyschedulekit import ExecutorRegistry, PyScheduleKitConfigurationError, TargetRef
from pyschedulekit.domain.time import Duration
from pyschedulekit.infrastructure.routing_executor import RoutingExecutor
from pyschedulekit.ports.cancellation import CancellationToken
from pyschedulekit.ports.executor import (
    ExecutorOutcome,
    PreparedTarget,
    UnsupportedTargetError,
)


@dataclass(frozen=True, slots=True)
class _Prepared:
    target: TargetRef


class _Executor:
    def __init__(self) -> None:
        self.executions = 0

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
        del prepared, timeout, cancellation_token, fencing_token, idempotency_key
        self.executions += 1
        return ExecutorOutcome()


def test_registry_register_resolve_and_target_kinds_are_deterministic() -> None:
    registry = ExecutorRegistry()
    workflow = _Executor()
    email = _Executor()

    registry.register(" workflow ", workflow)
    registry.register("email", email)

    assert registry.resolve("workflow") is workflow
    assert registry.resolve(" email ") is email
    assert registry.target_kinds == ("email", "workflow")


def test_registry_rejects_empty_and_duplicate_target_kinds() -> None:
    registry = ExecutorRegistry()
    executor = _Executor()

    with pytest.raises(PyScheduleKitConfigurationError, match="must not be empty"):
        registry.register("   ", executor)

    registry.register("workflow", executor)

    with pytest.raises(PyScheduleKitConfigurationError, match="already registered"):
        registry.register("workflow", _Executor())


def test_registry_replace_is_explicit() -> None:
    first = _Executor()
    second = _Executor()
    registry = ExecutorRegistry({"workflow": first})

    registry.register("workflow", second, replace=True)

    assert registry.resolve("workflow") is second


def test_registry_unregister_can_require_exact_executor_identity() -> None:
    registered = _Executor()
    different = _Executor()
    registry = ExecutorRegistry({"workflow": registered})

    assert not registry.unregister("workflow", different)
    assert registry.resolve("workflow") is registered

    assert registry.unregister("workflow", registered)
    assert not registry.unregister("workflow")

    with pytest.raises(UnsupportedTargetError, match="workflow"):
        registry.resolve("workflow")


def test_routing_executor_observes_dynamic_registry_mutation() -> None:
    registry = ExecutorRegistry({"python": _Executor()})
    router = RoutingExecutor(registry)
    workflow = _Executor()

    with pytest.raises(UnsupportedTargetError, match="workflow"):
        router.prepare(TargetRef.workflow("flow-1"))

    registry.register("workflow", workflow)
    prepared = router.prepare(TargetRef.workflow("flow-1"))
    outcome = router.execute(prepared)

    assert outcome.succeeded
    assert workflow.executions == 1
    assert router.target_kinds == ("python", "workflow")

    registry.unregister("workflow", workflow)
    with pytest.raises(UnsupportedTargetError, match="workflow"):
        router.prepare(TargetRef.workflow("flow-2"))


def test_registries_are_isolated_instances() -> None:
    first = ExecutorRegistry()
    second = ExecutorRegistry()
    executor = _Executor()

    first.register("workflow", executor)

    assert first.contains("workflow")
    assert not second.contains("workflow")
