"""Unit qualification for explicit executor plugin registration and activation."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from pyschedulekit.domain.schedule import TargetRef
from pyschedulekit.domain.time import Duration
from pyschedulekit.errors import PyScheduleKitConfigurationError
from pyschedulekit.infrastructure import executor_plugins
from pyschedulekit.infrastructure.executor_plugins import (
    EXECUTOR_ENTRY_POINT_GROUP,
    ExecutorPluginRegistry,
)
from pyschedulekit.ports.cancellation import CancellationToken
from pyschedulekit.ports.executor import ExecutorOutcome, PreparedTarget


@dataclass(frozen=True, slots=True)
class _Prepared:
    target: TargetRef


class _Executor:
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
        return ExecutorOutcome()


class _FakeEntryPoint:
    def __init__(
        self,
        *,
        name: str,
        value: str,
        loaded: object,
        load_counter: list[str],
    ) -> None:
        self.name = name
        self.value = value
        self.dist = None
        self._loaded = loaded
        self._load_counter = load_counter

    def load(self) -> object:
        self._load_counter.append(self.name)
        return self._loaded


def test_registry_registers_and_resolves_explicit_executor() -> None:
    registry = ExecutorPluginRegistry()
    executor = _Executor()

    registry.register("workflow", executor)

    assert registry.get("workflow") is executor
    assert registry.target_kinds == ("workflow",)


def test_registry_rejects_blank_duplicate_and_invalid_executor() -> None:
    registry = ExecutorPluginRegistry()
    executor = _Executor()
    registry.register("workflow", executor)

    with pytest.raises(PyScheduleKitConfigurationError, match="must not be empty"):
        registry.register("   ", executor)

    with pytest.raises(PyScheduleKitConfigurationError, match="already registered"):
        registry.register("workflow", _Executor())

    with pytest.raises(PyScheduleKitConfigurationError, match="prepare"):
        registry.register("invalid", object())  # type: ignore[arg-type]


def test_unregister_requires_exact_executor_identity() -> None:
    registry = ExecutorPluginRegistry()
    registered = _Executor()
    other = _Executor()
    registry.register("workflow", registered)

    assert not registry.unregister("workflow", other)
    assert registry.get("workflow") is registered

    assert registry.unregister("workflow", registered)
    assert registry.get("workflow") is None


def test_discovery_returns_metadata_without_loading_plugin_code(monkeypatch) -> None:
    loads: list[str] = []
    entry_point = _FakeEntryPoint(
        name="workflow",
        value="acme_scheduler:build_executor",
        loaded=lambda config: _Executor(),
        load_counter=loads,
    )

    monkeypatch.setattr(
        executor_plugins,
        "_installed_executor_entry_points",
        lambda: (entry_point,),
    )

    registry = ExecutorPluginRegistry()
    descriptors = registry.discover_entry_points()

    assert loads == []
    assert len(descriptors) == 1
    assert descriptors[0].target_kind == "workflow"
    assert descriptors[0].value == "acme_scheduler:build_executor"
    assert descriptors[0].distribution is None


def test_activation_loads_only_explicit_target_kind_and_passes_readonly_config(
    monkeypatch,
) -> None:
    loads: list[str] = []
    observed: dict[str, object] = {}

    def workflow_factory(config) -> _Executor:
        observed.update(config)
        with pytest.raises(TypeError):
            config["mutated"] = True
        return _Executor()

    workflow = _FakeEntryPoint(
        name="workflow",
        value="acme_scheduler:workflow",
        loaded=workflow_factory,
        load_counter=loads,
    )
    shell = _FakeEntryPoint(
        name="shell",
        value="acme_scheduler:shell",
        loaded=lambda config: _Executor(),
        load_counter=loads,
    )
    monkeypatch.setattr(
        executor_plugins,
        "_installed_executor_entry_points",
        lambda: (workflow, shell),
    )

    registry = ExecutorPluginRegistry()
    activated = registry.activate_entry_point(
        "workflow",
        config={"endpoint": "internal://workflow"},
    )

    assert loads == ["workflow"]
    assert observed == {"endpoint": "internal://workflow"}
    assert registry.get("workflow") is activated
    assert registry.get("shell") is None


def test_activation_rejects_missing_duplicate_and_non_factory_plugins(monkeypatch) -> None:
    registry = ExecutorPluginRegistry()

    monkeypatch.setattr(
        executor_plugins,
        "_installed_executor_entry_points",
        lambda: (),
    )
    with pytest.raises(PyScheduleKitConfigurationError, match="No installed"):
        registry.activate_entry_point("workflow")

    duplicate_a = _FakeEntryPoint(
        name="workflow",
        value="a:factory",
        loaded=lambda config: _Executor(),
        load_counter=[],
    )
    duplicate_b = _FakeEntryPoint(
        name="workflow",
        value="b:factory",
        loaded=lambda config: _Executor(),
        load_counter=[],
    )
    monkeypatch.setattr(
        executor_plugins,
        "_installed_executor_entry_points",
        lambda: (duplicate_a, duplicate_b),
    )
    with pytest.raises(PyScheduleKitConfigurationError, match="Multiple installed"):
        registry.activate_entry_point("workflow")

    invalid = _FakeEntryPoint(
        name="workflow",
        value="invalid:value",
        loaded=SimpleNamespace(),
        load_counter=[],
    )
    monkeypatch.setattr(
        executor_plugins,
        "_installed_executor_entry_points",
        lambda: (invalid,),
    )
    with pytest.raises(PyScheduleKitConfigurationError, match="callable factory"):
        registry.activate_entry_point("workflow")


def test_entry_point_group_is_stable() -> None:
    assert EXECUTOR_ENTRY_POINT_GROUP == "pyschedulekit.executors"
