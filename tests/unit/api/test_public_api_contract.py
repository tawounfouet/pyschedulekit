"""LOT-34 fitness tests for the stable public API contract."""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError
from importlib.metadata import version

import pytest

import pyschedulekit
import pyschedulekit.api as public_api
import pyschedulekit.experimental as experimental
from pyschedulekit import (
    Duration,
    ExecutionNotFoundError,
    IntervalTrigger,
    PyScheduleKitNotFoundError,
    PyScheduleKitStateError,
    PyScheduleKitTargetError,
    RuntimeAlreadyRunningError,
    ScheduleNotFoundError,
    Scheduler,
)
from pyschedulekit.api._manifest import (
    API_ONLY_V1_PUBLIC_NAMES,
    LEGACY_ROOT_NAMES,
    ROOT_V1_PUBLIC_NAMES,
    STABLE_PUBLIC_NAMES,
)
from pyschedulekit.testing import MutableClock


def _parameter_names(callable_object: object) -> tuple[str, ...]:
    return tuple(inspect.signature(callable_object).parameters)


def test_t_public_api_001_manifest_is_sorted_unique_and_exact() -> None:
    assert tuple(sorted(STABLE_PUBLIC_NAMES)) == STABLE_PUBLIC_NAMES
    assert len(STABLE_PUBLIC_NAMES) == len(set(STABLE_PUBLIC_NAMES))
    assert public_api.__all__ == list(STABLE_PUBLIC_NAMES)
    assert pyschedulekit.__all__ == [*ROOT_V1_PUBLIC_NAMES, "__version__"]

    for name in ROOT_V1_PUBLIC_NAMES:
        assert getattr(pyschedulekit, name) is getattr(public_api, name)

    for name in API_ONLY_V1_PUBLIC_NAMES:
        assert hasattr(public_api, name)
        assert not hasattr(pyschedulekit, name)

    assert not set(LEGACY_ROOT_NAMES).intersection(STABLE_PUBLIC_NAMES)
    assert not set(LEGACY_ROOT_NAMES).intersection(pyschedulekit.__all__)


def test_t_public_api_002_legacy_root_names_are_removed_before_v1() -> None:
    for name in LEGACY_ROOT_NAMES:
        assert not hasattr(pyschedulekit, name)
        with pytest.raises(AttributeError):
            getattr(pyschedulekit, name)
        assert getattr(experimental, name) is not None


def test_t_public_api_003_public_error_hierarchy_is_catchable_by_category() -> None:
    assert issubclass(ScheduleNotFoundError, PyScheduleKitNotFoundError)
    assert issubclass(ScheduleNotFoundError, LookupError)
    assert issubclass(ExecutionNotFoundError, PyScheduleKitNotFoundError)
    assert issubclass(ExecutionNotFoundError, LookupError)
    assert issubclass(RuntimeAlreadyRunningError, PyScheduleKitStateError)
    assert issubclass(RuntimeAlreadyRunningError, RuntimeError)
    assert issubclass(public_api.TargetResolutionError, PyScheduleKitTargetError)
    assert issubclass(public_api.TargetResolutionError, RuntimeError)


def test_t_public_api_004_scheduler_signature_parameter_contract() -> None:
    assert _parameter_names(Scheduler) == (
        "clock",
        "uow_factory",
        "calendar_provider",
        "registry",
        "http_registry",
        "executors",
        "executor_registry",
        "worker_id",
        "claim_ttl",
        "lease_heartbeat_interval",
        "admission_lock_ttl",
        "materialization_lease_ttl",
        "observation_sink",
    )
    assert _parameter_names(Scheduler.register_target) == ("self", "reference", "target")
    assert _parameter_names(Scheduler.register_async_target) == ("self", "reference", "target")
    assert _parameter_names(Scheduler.register_executor) == ("self", "target_kind", "executor")
    assert _parameter_names(Scheduler.register_http_target) == ("self", "reference", "request")
    assert _parameter_names(Scheduler.add_schedule) == (
        "self",
        "target",
        "trigger",
        "id",
        "timezone",
        "calendar",
        "misfire",
        "concurrency",
        "retry",
        "timeout",
    )
    assert _parameter_names(Scheduler.inspect_schedule) == ("self", "schedule_id")
    assert _parameter_names(Scheduler.inspect_execution) == ("self", "execution_id")
    assert _parameter_names(Scheduler.pause_schedule) == ("self", "schedule_id")
    assert _parameter_names(Scheduler.resume_schedule) == ("self", "schedule_id")
    assert _parameter_names(Scheduler.cancel_schedule) == ("self", "schedule_id")
    assert _parameter_names(Scheduler.cancel_execution) == ("self", "execution_id")
    assert _parameter_names(Scheduler.recover) == ("self", "limit")
    assert _parameter_names(Scheduler.reconcile) == ("self", "limit")
    assert _parameter_names(Scheduler.dispatch_outbox) == ("self", "publisher", "limit")
    assert _parameter_names(Scheduler.cleanup) == ("self", "policy", "limit")
    assert _parameter_names(Scheduler.run_pending) == ("self", "limit")
    assert _parameter_names(Scheduler.run_forever) == (
        "self",
        "max_sleep",
        "poll_interval",
        "limit",
    )
    assert _parameter_names(Scheduler.stop) == ("self",)
    assert _parameter_names(Scheduler.shutdown) == ("self", "mode", "timeout")


def test_t_public_api_005_scheduler_never_returns_mutable_execution_aggregate() -> None:
    clock = MutableClock(pyschedulekit.Instant.parse("2026-01-01T10:00:00+00:00"))
    scheduler = Scheduler(clock=clock)
    scheduler.add_schedule(
        id="snapshot-only",
        target=lambda: None,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=pyschedulekit.Instant.parse("2026-01-01T10:10:00+00:00"),
        ),
    )
    clock.advance(Duration.minutes(10))

    cycle = scheduler.run_pending()
    execution = cycle.executions[0].execution

    assert isinstance(execution, pyschedulekit.ExecutionSnapshot)
    with pytest.raises(FrozenInstanceError):
        execution.attempt_count = 99  # type: ignore[misc]


def test_t_public_api_006_installed_version_matches_runtime_version() -> None:
    assert version("pyschedulekit") == pyschedulekit.__version__ == "0.1.0a4"
