"""Stable convenience imports for PyScheduleKit."""

# ruff: noqa: I001

from __future__ import annotations

import warnings
from importlib import import_module

from pyschedulekit._version import __version__ as __version__
from pyschedulekit.api import AdmissionSnapshot as AdmissionSnapshot
from pyschedulekit.api import AsyncioExecutor as AsyncioExecutor
from pyschedulekit.api import AsyncPythonTargetRegistry as AsyncPythonTargetRegistry
from pyschedulekit.api import AttemptId as AttemptId
from pyschedulekit.api import CancellationToken as CancellationToken
from pyschedulekit.api import CleanupResult as CleanupResult
from pyschedulekit.api import Clock as Clock
from pyschedulekit.api import ConcurrencyDecision as ConcurrencyDecision
from pyschedulekit.api import ConcurrencyDecisionAction as ConcurrencyDecisionAction
from pyschedulekit.api import ConcurrencyMode as ConcurrencyMode
from pyschedulekit.api import ConcurrencyOverflowPolicy as ConcurrencyOverflowPolicy
from pyschedulekit.api import ConcurrencyPolicy as ConcurrencyPolicy
from pyschedulekit.api import CrashRecoveryActiveRuntimeError as CrashRecoveryActiveRuntimeError
from pyschedulekit.api import CrashRecoveryError as CrashRecoveryError
from pyschedulekit.api import CrashRecoveryIncompleteError as CrashRecoveryIncompleteError
from pyschedulekit.api import CrashRecoveryResult as CrashRecoveryResult
from pyschedulekit.api import CronAmbiguousTimePolicy as CronAmbiguousTimePolicy
from pyschedulekit.api import CronDialect as CronDialect
from pyschedulekit.api import CronNonexistentTimePolicy as CronNonexistentTimePolicy
from pyschedulekit.api import CronTrigger as CronTrigger
from pyschedulekit.api import DateTrigger as DateTrigger
from pyschedulekit.api import Duration as Duration
from pyschedulekit.api import ExecutionCancelledError as ExecutionCancelledError
from pyschedulekit.api import ExecutionId as ExecutionId
from pyschedulekit.api import ExecutionNotFoundError as ExecutionNotFoundError
from pyschedulekit.api import ExecutionPolicySnapshot as ExecutionPolicySnapshot
from pyschedulekit.api import ExecutionRunSnapshot as ExecutionRunSnapshot
from pyschedulekit.api import ExecutionSnapshot as ExecutionSnapshot
from pyschedulekit.api import ExecutionState as ExecutionState
from pyschedulekit.api import Executor as Executor
from pyschedulekit.api import ExecutorOutcome as ExecutorOutcome
from pyschedulekit.api import ExponentialBackoff as ExponentialBackoff
from pyschedulekit.api import Failure as Failure
from pyschedulekit.api import FailureCategory as FailureCategory
from pyschedulekit.api import FixedBackoff as FixedBackoff
from pyschedulekit.api import GracePeriod as GracePeriod
from pyschedulekit.api import HttpExecutor as HttpExecutor
from pyschedulekit.api import HttpMethod as HttpMethod
from pyschedulekit.api import HttpRequestSpec as HttpRequestSpec
from pyschedulekit.api import HttpTargetRegistry as HttpTargetRegistry
from pyschedulekit.api import InMemoryObservationSink as InMemoryObservationSink
from pyschedulekit.api import Instant as Instant
from pyschedulekit.api import IntervalTrigger as IntervalTrigger
from pyschedulekit.api import LocalExecutor as LocalExecutor
from pyschedulekit.api import MisfirePolicy as MisfirePolicy
from pyschedulekit.api import MisfirePolicyAction as MisfirePolicyAction
from pyschedulekit.api import NoBackoff as NoBackoff
from pyschedulekit.api import Observation as Observation
from pyschedulekit.api import ObservationSink as ObservationSink
from pyschedulekit.api import OutboxDispatchResult as OutboxDispatchResult
from pyschedulekit.api import OutboxMessage as OutboxMessage
from pyschedulekit.api import OutboxMessageId as OutboxMessageId
from pyschedulekit.api import OutboxPublishError as OutboxPublishError
from pyschedulekit.api import OutboxPublisher as OutboxPublisher
from pyschedulekit.api import OutboxState as OutboxState
from pyschedulekit.api import PreparedTarget as PreparedTarget
from pyschedulekit.api import PyScheduleKitConfigurationError as PyScheduleKitConfigurationError
from pyschedulekit.api import PyScheduleKitDeprecationWarning as PyScheduleKitDeprecationWarning
from pyschedulekit.api import PyScheduleKitError as PyScheduleKitError
from pyschedulekit.api import PyScheduleKitNotFoundError as PyScheduleKitNotFoundError
from pyschedulekit.api import PyScheduleKitStateError as PyScheduleKitStateError
from pyschedulekit.api import PyScheduleKitTargetError as PyScheduleKitTargetError
from pyschedulekit.api import PythonTargetRegistry as PythonTargetRegistry
from pyschedulekit.api import ReconciliationActiveRuntimeError as ReconciliationActiveRuntimeError
from pyschedulekit.api import ReconciliationIncompleteError as ReconciliationIncompleteError
from pyschedulekit.api import ReconciliationIssue as ReconciliationIssue
from pyschedulekit.api import ReconciliationResult as ReconciliationResult
from pyschedulekit.api import RequestId as RequestId
from pyschedulekit.api import RetentionPolicy as RetentionPolicy
from pyschedulekit.api import RetryDecision as RetryDecision
from pyschedulekit.api import RetryDecisionReason as RetryDecisionReason
from pyschedulekit.api import RetryPolicy as RetryPolicy
from pyschedulekit.api import RoutingExecutor as RoutingExecutor
from pyschedulekit.api import RunPendingError as RunPendingError
from pyschedulekit.api import RunPendingResult as RunPendingResult
from pyschedulekit.api import RuntimeAlreadyRunningError as RuntimeAlreadyRunningError
from pyschedulekit.api import ScheduleId as ScheduleId
from pyschedulekit.api import ScheduleNotFoundError as ScheduleNotFoundError
from pyschedulekit.api import ScheduleSnapshot as ScheduleSnapshot
from pyschedulekit.api import ScheduleState as ScheduleState
from pyschedulekit.api import Scheduler as Scheduler
from pyschedulekit.api import SchedulerHealth as SchedulerHealth
from pyschedulekit.api import SchedulerReadiness as SchedulerReadiness
from pyschedulekit.api import ShutdownMode as ShutdownMode
from pyschedulekit.api import ShutdownResult as ShutdownResult
from pyschedulekit.api import SqliteUnitOfWorkFactory as SqliteUnitOfWorkFactory
from pyschedulekit.api import TargetRef as TargetRef
from pyschedulekit.api import TargetResolutionError as TargetResolutionError
from pyschedulekit.api import Timezone as Timezone
from pyschedulekit.api import Trigger as Trigger
from pyschedulekit.api import UnitOfWorkFactory as UnitOfWorkFactory
from pyschedulekit.api import UnsupportedTargetError as UnsupportedTargetError
from pyschedulekit.api import WorkerId as WorkerId
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
