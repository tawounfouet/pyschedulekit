"""Stable public API surface for PyScheduleKit."""

# ruff: noqa: F401

from pyschedulekit.api._manifest import STABLE_PUBLIC_NAMES
from pyschedulekit.api.results import AdmissionSnapshot, ExecutionRunSnapshot, RunPendingResult
from pyschedulekit.api.scheduler import Scheduler
from pyschedulekit.application.execution_service import ExecutionNotFoundError
from pyschedulekit.application.operations import (
    ExecutionSnapshot,
    ScheduleNotFoundError,
    SchedulerHealth,
    SchedulerReadiness,
    ScheduleSnapshot,
)
from pyschedulekit.application.outbox import OutboxDispatchResult, OutboxPublishError
from pyschedulekit.application.reconciliation import (
    ReconciliationActiveRuntimeError,
    ReconciliationIncompleteError,
    ReconciliationIssue,
    ReconciliationResult,
)
from pyschedulekit.application.recovery import (
    CrashRecoveryActiveRuntimeError,
    CrashRecoveryError,
    CrashRecoveryIncompleteError,
    CrashRecoveryResult,
)
from pyschedulekit.application.retention import CleanupResult, RetentionPolicy
from pyschedulekit.application.run_pending import RunPendingError
from pyschedulekit.application.runtime import RuntimeAlreadyRunningError
from pyschedulekit.application.shutdown import ShutdownMode, ShutdownResult
from pyschedulekit.domain.claim import WorkerId
from pyschedulekit.domain.concurrency import (
    ConcurrencyDecision,
    ConcurrencyDecisionAction,
    ConcurrencyMode,
    ConcurrencyOverflowPolicy,
    ConcurrencyPolicy,
)
from pyschedulekit.domain.execution import (
    AttemptId,
    ExecutionId,
    ExecutionPolicySnapshot,
    ExecutionState,
    Failure,
    FailureCategory,
)
from pyschedulekit.domain.execution_request import RequestId
from pyschedulekit.domain.misfire import MisfirePolicy, MisfirePolicyAction
from pyschedulekit.domain.outbox import OutboxMessage, OutboxMessageId, OutboxState
from pyschedulekit.domain.retry import (
    ExponentialBackoff,
    FixedBackoff,
    NoBackoff,
    RetryDecision,
    RetryDecisionReason,
    RetryPolicy,
)
from pyschedulekit.domain.schedule import ScheduleId, ScheduleState, TargetRef
from pyschedulekit.domain.time import Duration, GracePeriod, Instant, Timezone
from pyschedulekit.domain.trigger import Trigger
from pyschedulekit.domain.triggers import (
    CronAmbiguousTimePolicy,
    CronDialect,
    CronNonexistentTimePolicy,
    CronTrigger,
    DateTrigger,
    IntervalTrigger,
)
from pyschedulekit.errors import (
    PyScheduleKitConfigurationError,
    PyScheduleKitDeprecationWarning,
    PyScheduleKitError,
    PyScheduleKitNotFoundError,
    PyScheduleKitStateError,
    PyScheduleKitTargetError,
)
from pyschedulekit.infrastructure.http_executor import (
    HttpExecutor,
    HttpMethod,
    HttpRequestSpec,
    HttpTargetRegistry,
)
from pyschedulekit.infrastructure.local_executor import LocalExecutor, PythonTargetRegistry
from pyschedulekit.infrastructure.observability import InMemoryObservationSink
from pyschedulekit.infrastructure.routing_executor import RoutingExecutor
from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory
from pyschedulekit.ports.cancellation import CancellationToken, ExecutionCancelledError
from pyschedulekit.ports.executor import (
    Executor,
    ExecutorOutcome,
    PreparedTarget,
    TargetResolutionError,
    UnsupportedTargetError,
)
from pyschedulekit.ports.observability import Observation, ObservationSink
from pyschedulekit.ports.outbox import OutboxPublisher
from pyschedulekit.ports.persistence import UnitOfWorkFactory
from pyschedulekit.ports.time import Clock

__all__ = list(STABLE_PUBLIC_NAMES)
