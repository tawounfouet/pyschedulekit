"""End-to-end qualification for explicit Executor plugins."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from pyschedulekit import (
    Duration,
    ExecutorOutcome,
    ExecutorRegistry,
    IntervalTrigger,
    Scheduler,
    TargetRef,
)
from pyschedulekit.domain.time import Instant
from pyschedulekit.ports.cancellation import CancellationToken
from pyschedulekit.ports.executor import PreparedTarget
from pyschedulekit.testing import MutableClock


@dataclass(frozen=True, slots=True)
class _PreparedPluginTarget:
    target: TargetRef


class _PluginExecutor:
    def __init__(self) -> None:
        self.references: list[str] = []

    def prepare(self, target: TargetRef) -> PreparedTarget:
        return _PreparedPluginTarget(target)

    def execute(
        self,
        prepared: PreparedTarget,
        *,
        timeout: Duration | None = None,
        cancellation_token: CancellationToken | None = None,
        fencing_token: int | None = None,
        idempotency_key: str | None = None,
    ) -> ExecutorOutcome:
        del timeout, cancellation_token, fencing_token, idempotency_key
        self.references.append(prepared.target.reference)
        return ExecutorOutcome()


def _instant(minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, minute, tzinfo=UTC))


def test_scheduler_executes_plugin_registered_after_construction() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    plugin = _PluginExecutor()

    scheduler.executor_registry.register("workflow", plugin)
    scheduler.add_schedule(
        id="plugin-schedule",
        target=TargetRef.workflow("invoice-close"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(10),
        ),
    )

    clock.advance(Duration.minutes(10))
    result = scheduler.run_pending()

    assert result.succeeded == 1
    assert plugin.references == ["invoice-close"]


def test_scheduler_instances_keep_executor_registries_isolated() -> None:
    first = Scheduler(clock=MutableClock(_instant()))
    second = Scheduler(clock=MutableClock(_instant()))
    plugin = _PluginExecutor()

    first.executor_registry.register("workflow", plugin)

    assert first.executor_registry.contains("workflow")
    assert not second.executor_registry.contains("workflow")
    assert first.executor_registry is not second.executor_registry


def test_scheduler_uses_explicit_registry_and_preserves_preloaded_plugin() -> None:
    plugin = _PluginExecutor()
    registry = ExecutorRegistry({"workflow": plugin})

    scheduler = Scheduler(
        clock=MutableClock(_instant()),
        executor_registry=registry,
    )

    assert scheduler.executor_registry is registry
    assert registry.resolve("workflow") is plugin
    assert registry.target_kinds == ("http", "python", "python_async", "workflow")


def test_legacy_executors_mapping_remains_an_explicit_override() -> None:
    preloaded = _PluginExecutor()
    override = _PluginExecutor()
    registry = ExecutorRegistry({"workflow": preloaded})

    scheduler = Scheduler(
        clock=MutableClock(_instant()),
        executor_registry=registry,
        executors={"workflow": override},
    )

    assert scheduler.executor_registry.resolve("workflow") is override
