"""Stable convenience imports for PyScheduleKit."""

# ruff: noqa: F401, I001

from __future__ import annotations

import warnings
from importlib import import_module

from pyschedulekit._version import __version__
from pyschedulekit.api import (
    AdmissionSnapshot,
    AttemptId,
    CancellationToken,
    CleanupResult,
    Clock,
    ConcurrencyDecision,
    ConcurrencyDecisionAction,
    ConcurrencyMode,
    ConcurrencyOverflowPolicy,
    ConcurrencyPolicy,
    CrashRecoveryActiveRuntimeError,
    CrashRecoveryError,
    CrashRecoveryIncompleteError,
    CrashRecoveryResult,
    CronAmbiguousTimePolicy,
    CronDialect,
    CronNonexistentTimePolicy,
    CronTrigger,
    DateTrigger,
    Duration,
    ExecutionCancelledError,
    ExecutionId,
    ExecutionNotFoundError,
    ExecutionPolicySnapshot,
    ExecutionRunSnapshot,
    ExecutionSnapshot,
    ExecutionState,
    Executor,
    ExecutorOutcome,
    ExponentialBackoff,
    Failure,
    FailureCategory,
    FixedBackoff,
    GracePeriod,
    HttpExecutor,
    HttpMethod,
    HttpRequestSpec,
    HttpTargetRegistry,
    InMemoryObservationSink,
    Instant,
    IntervalTrigger,
    LocalExecutor,
    MisfirePolicy,
    MisfirePolicyAction,
    NoBackoff,
    Observation,
    ObservationSink,
    OutboxDispatchResult,
    OutboxMessage,
    OutboxMessageId,
    OutboxPublishError,
    OutboxPublisher,
    OutboxState,
    PreparedTarget,
    PyScheduleKitConfigurationError,
    PyScheduleKitDeprecationWarning,
    PyScheduleKitError,
    PyScheduleKitNotFoundError,
    PyScheduleKitStateError,
    PyScheduleKitTargetError,
    PythonTargetRegistry,
    ReconciliationActiveRuntimeError,
    ReconciliationIncompleteError,
    ReconciliationIssue,
    ReconciliationResult,
    RequestId,
    RetentionPolicy,
    RetryDecision,
    RetryDecisionReason,
    RetryPolicy,
    RoutingExecutor,
    RunPendingError,
    RunPendingResult,
    RuntimeAlreadyRunningError,
    ScheduleId,
    ScheduleNotFoundError,
    ScheduleSnapshot,
    ScheduleState,
    Scheduler,
    SchedulerHealth,
    SchedulerReadiness,
    ShutdownMode,
    ShutdownResult,
    SqliteUnitOfWorkFactory,
    TargetRef,
    TargetResolutionError,
    Timezone,
    Trigger,
    UnitOfWorkFactory,
    UnsupportedTargetError,
    WorkerId,
)
from pyschedulekit.api._manifest import LEGACY_ROOT_NAMES, STABLE_PUBLIC_NAMES

__all__ = [*STABLE_PUBLIC_NAMES, "__version__"]

_LEGACY_ROOT_NAMES = frozenset(LEGACY_ROOT_NAMES)


def __getattr__(name: str) -> object:
    if name not in _LEGACY_ROOT_NAMES:
        raise AttributeError(f"module 'pyschedulekit' has no attribute {name!r}")

    warnings.warn(
        (
            f"pyschedulekit.{name} is no longer part of the stable root API; "
            f"import it from pyschedulekit.experimental instead."
        ),
        PyScheduleKitDeprecationWarning,
        stacklevel=2,
    )
    experimental = import_module("pyschedulekit.experimental")
    return getattr(experimental, name)


def __dir__() -> list[str]:
    return sorted({*globals(), *_LEGACY_ROOT_NAMES})
