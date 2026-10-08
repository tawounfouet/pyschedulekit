"""Stable convenience imports for PyScheduleKit."""

from __future__ import annotations

import warnings
from importlib import import_module

from pyschedulekit._version import __version__ as __version__
from pyschedulekit.api import (
    AdmissionSnapshot as AdmissionSnapshot,
    AttemptId as AttemptId,
    CancellationToken as CancellationToken,
    CleanupResult as CleanupResult,
    Clock as Clock,
    ConcurrencyDecision as ConcurrencyDecision,
    ConcurrencyDecisionAction as ConcurrencyDecisionAction,
    ConcurrencyMode as ConcurrencyMode,
    ConcurrencyOverflowPolicy as ConcurrencyOverflowPolicy,
    ConcurrencyPolicy as ConcurrencyPolicy,
    CrashRecoveryActiveRuntimeError as CrashRecoveryActiveRuntimeError,
    CrashRecoveryError as CrashRecoveryError,
    CrashRecoveryIncompleteError as CrashRecoveryIncompleteError,
    CrashRecoveryResult as CrashRecoveryResult,
    CronAmbiguousTimePolicy as CronAmbiguousTimePolicy,
    CronDialect as CronDialect,
    CronNonexistentTimePolicy as CronNonexistentTimePolicy,
    CronTrigger as CronTrigger,
    DateTrigger as DateTrigger,
    Duration as Duration,
    ExecutionCancelledError as ExecutionCancelledError,
    ExecutionId as ExecutionId,
    ExecutionNotFoundError as ExecutionNotFoundError,
    ExecutionPolicySnapshot as ExecutionPolicySnapshot,
    ExecutionRunSnapshot as ExecutionRunSnapshot,
    ExecutionSnapshot as ExecutionSnapshot,
    ExecutionState as ExecutionState,
    Executor as Executor,
    ExecutorOutcome as ExecutorOutcome,
    ExponentialBackoff as ExponentialBackoff,
    Failure as Failure,
    FailureCategory as FailureCategory,
    FixedBackoff as FixedBackoff,
    GracePeriod as GracePeriod,
    HttpExecutor as HttpExecutor,
    HttpMethod as HttpMethod,
    HttpRequestSpec as HttpRequestSpec,
    HttpTargetRegistry as HttpTargetRegistry,
    InMemoryObservationSink as InMemoryObservationSink,
    Instant as Instant,
    IntervalTrigger as IntervalTrigger,
    LocalExecutor as LocalExecutor,
    MisfirePolicy as MisfirePolicy,
    MisfirePolicyAction as MisfirePolicyAction,
    NoBackoff as NoBackoff,
    Observation as Observation,
    ObservationSink as ObservationSink,
    OutboxDispatchResult as OutboxDispatchResult,
    OutboxMessage as OutboxMessage,
    OutboxMessageId as OutboxMessageId,
    OutboxPublishError as OutboxPublishError,
    OutboxPublisher as OutboxPublisher,
    OutboxState as OutboxState,
    PreparedTarget as PreparedTarget,
    PyScheduleKitConfigurationError as PyScheduleKitConfigurationError,
    PyScheduleKitDeprecationWarning as PyScheduleKitDeprecationWarning,
    PyScheduleKitError as PyScheduleKitError,
    PyScheduleKitNotFoundError as PyScheduleKitNotFoundError,
    PyScheduleKitStateError as PyScheduleKitStateError,
    PyScheduleKitTargetError as PyScheduleKitTargetError,
    PythonTargetRegistry as PythonTargetRegistry,
    ReconciliationActiveRuntimeError as ReconciliationActiveRuntimeError,
    ReconciliationIncompleteError as ReconciliationIncompleteError,
    ReconciliationIssue as ReconciliationIssue,
    ReconciliationResult as ReconciliationResult,
    RequestId as RequestId,
    RetentionPolicy as RetentionPolicy,
    RetryDecision as RetryDecision,
    RetryDecisionReason as RetryDecisionReason,
    RetryPolicy as RetryPolicy,
    RoutingExecutor as RoutingExecutor,
    RunPendingError as RunPendingError,
    RunPendingResult as RunPendingResult,
    RuntimeAlreadyRunningError as RuntimeAlreadyRunningError,
    ScheduleId as ScheduleId,
    ScheduleNotFoundError as ScheduleNotFoundError,
    ScheduleSnapshot as ScheduleSnapshot,
    ScheduleState as ScheduleState,
    Scheduler as Scheduler,
    SchedulerHealth as SchedulerHealth,
    SchedulerReadiness as SchedulerReadiness,
    ShutdownMode as ShutdownMode,
    ShutdownResult as ShutdownResult,
    SqliteUnitOfWorkFactory as SqliteUnitOfWorkFactory,
    TargetRef as TargetRef,
    TargetResolutionError as TargetResolutionError,
    Timezone as Timezone,
    Trigger as Trigger,
    UnitOfWorkFactory as UnitOfWorkFactory,
    UnsupportedTargetError as UnsupportedTargetError,
    WorkerId as WorkerId,
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
