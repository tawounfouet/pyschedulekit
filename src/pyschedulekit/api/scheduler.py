"""Public Scheduler facade for the first in-memory vertical slice."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from threading import Lock
from time import monotonic
from uuid import uuid4

from pyschedulekit.api.results import RunPendingResult
from pyschedulekit.application.admission_lock import ScheduleAdmissionLockCoordinator
from pyschedulekit.application.claims import ExecutionClaimCoordinator
from pyschedulekit.application.concurrency import ConcurrencyCoordinator
from pyschedulekit.application.execution_runner import ExecutionRunner
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.application.materialization import ScheduleMaterializationCoordinator
from pyschedulekit.application.observability import Observer
from pyschedulekit.application.operations import (
    ExecutionSnapshot,
    SchedulerHealth,
    SchedulerOperations,
    SchedulerReadiness,
    ScheduleSnapshot,
)
from pyschedulekit.application.outbox import OutboxDispatcher, OutboxDispatchResult
from pyschedulekit.application.reconciliation import (
    ReconciliationActiveRuntimeError,
    ReconciliationIncompleteError,
    ReconciliationResult,
    ReconciliationService,
)
from pyschedulekit.application.recovery import (
    CrashRecoveryActiveRuntimeError,
    CrashRecoveryIncompleteError,
    CrashRecoveryResult,
    CrashRecoveryService,
)
from pyschedulekit.application.retention import CleanupResult, RetentionPolicy, RetentionService
from pyschedulekit.application.run_pending import RunPendingService
from pyschedulekit.application.runtime import ContinuousSchedulerLoop
from pyschedulekit.application.scheduler_engine import SchedulerEngine
from pyschedulekit.application.shutdown import (
    ShutdownCoordinator,
    ShutdownMode,
    ShutdownResult,
)
from pyschedulekit.application.wakeup import WakeUpPlanner
from pyschedulekit.domain.claim import WorkerId
from pyschedulekit.domain.concurrency import ConcurrencyPolicy
from pyschedulekit.domain.execution import ExecutionId, ExecutionState
from pyschedulekit.domain.misfire import MisfirePolicy
from pyschedulekit.domain.retry import RetryPolicy
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Timezone
from pyschedulekit.domain.trigger import Trigger
from pyschedulekit.domain.triggers import CronTrigger
from pyschedulekit.errors import PyScheduleKitConfigurationError
from pyschedulekit.infrastructure.asyncio_executor import (
    AsyncioExecutor,
    AsyncPythonTargetRegistry,
)
from pyschedulekit.infrastructure.cancellation import InMemoryCancellationController
from pyschedulekit.infrastructure.executor_registry import ExecutorRegistry
from pyschedulekit.infrastructure.http_executor import (
    HttpExecutor,
    HttpRequestSpec,
    HttpTargetRegistry,
)
from pyschedulekit.infrastructure.local_executor import (
    LocalExecutor,
    PythonTargetRegistry,
)
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.infrastructure.routing_executor import RoutingExecutor
from pyschedulekit.infrastructure.runtime import EventLoopWaiter
from pyschedulekit.infrastructure.time import SystemClock
from pyschedulekit.ports.executor import Executor
from pyschedulekit.ports.observability import ObservationSink
from pyschedulekit.ports.outbox import OutboxPublisher
from pyschedulekit.ports.persistence import UnitOfWorkFactory
from pyschedulekit.ports.time import Clock


class Scheduler:
    """Small public facade over the first qualified in-memory scheduling slice."""

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        uow_factory: UnitOfWorkFactory | None = None,
        registry: PythonTargetRegistry | None = None,
        http_registry: HttpTargetRegistry | None = None,
        executors: Mapping[str, Executor] | None = None,
        executor_registry: ExecutorRegistry | None = None,
        worker_id: str | WorkerId | None = None,
        claim_ttl: Duration | None = None,
        lease_heartbeat_interval: Duration | None = None,
        admission_lock_ttl: Duration | None = None,
        materialization_lease_ttl: Duration | None = None,
        observation_sink: ObservationSink | None = None,
    ) -> None:
        self._clock: Clock = clock if clock is not None else SystemClock()
        self._uow_factory: UnitOfWorkFactory = (
            uow_factory if uow_factory is not None else InMemoryUnitOfWorkFactory()
        )
        self._registry = registry if registry is not None else PythonTargetRegistry()
        self._async_registry = AsyncPythonTargetRegistry()
        self._http_registry = http_registry if http_registry is not None else HttpTargetRegistry()
        self._executor_registry = (
            executor_registry if executor_registry is not None else ExecutorRegistry()
        )
        builtin_executors: dict[str, Executor] = {
            "python": LocalExecutor(
                registry=self._registry,
                clock=self._clock,
            ),
            "python_async": AsyncioExecutor(
                registry=self._async_registry,
                clock=self._clock,
            ),
            "http": HttpExecutor(
                registry=self._http_registry,
                clock=self._clock,
            ),
        }
        for kind, executor in builtin_executors.items():
            if not self._executor_registry.contains(kind):
                self._executor_registry.register(kind, executor)
        if executors is not None:
            for kind, executor in executors.items():
                self._executor_registry.register(kind, executor, replace=True)
        self._executor = RoutingExecutor(self._executor_registry)
        self._worker_id = (
            worker_id if isinstance(worker_id, WorkerId) else WorkerId(worker_id or uuid4().hex)
        )
        self._claim_ttl = claim_ttl if claim_ttl is not None else Duration.seconds(30)
        self._lease_heartbeat_interval = (
            lease_heartbeat_interval
            if lease_heartbeat_interval is not None
            else Duration.seconds(self._claim_ttl.total_seconds / 3)
        )
        if self._lease_heartbeat_interval.total_seconds <= 0:
            raise PyScheduleKitConfigurationError(
                "lease_heartbeat_interval must be greater than zero."
            )
        if self._lease_heartbeat_interval >= self._claim_ttl:
            raise PyScheduleKitConfigurationError(
                "lease_heartbeat_interval must be shorter than claim_ttl."
            )
        self._admission_lock_ttl = (
            admission_lock_ttl if admission_lock_ttl is not None else Duration.seconds(5)
        )
        self._materialization_lease_ttl = (
            materialization_lease_ttl
            if materialization_lease_ttl is not None
            else Duration.seconds(5)
        )
        self._observer = Observer(observation_sink)
        self._operations = SchedulerOperations(
            clock=self._clock,
            uow_factory=self._uow_factory,
        )
        self._retention_service = RetentionService(
            clock=self._clock,
            uow_factory=self._uow_factory,
            observer=self._observer,
        )
        self._claim_coordinator = ExecutionClaimCoordinator(
            uow_factory=self._uow_factory,
            worker_id=self._worker_id,
            ttl=self._claim_ttl,
        )

        self._admission_lock_coordinator = ScheduleAdmissionLockCoordinator(
            uow_factory=self._uow_factory,
            worker_id=self._worker_id,
            ttl=self._admission_lock_ttl,
        )
        self._materialization_coordinator = ScheduleMaterializationCoordinator(
            uow_factory=self._uow_factory,
            worker_id=self._worker_id,
            ttl=self._materialization_lease_ttl,
        )

        self._execution_service = ExecutionService(uow_factory=self._uow_factory)
        self._recovery_service = CrashRecoveryService(
            clock=self._clock,
            uow_factory=self._uow_factory,
            claim_coordinator=self._claim_coordinator,
        )
        self._recovery_lock = Lock()
        self._recovery_done = False
        self._last_recovery_result: CrashRecoveryResult | None = None
        self._reconciliation_service = ReconciliationService(
            uow_factory=self._uow_factory,
        )
        self._reconciliation_lock = Lock()
        self._reconciliation_done = False
        self._last_reconciliation_result: ReconciliationResult | None = None
        self._cancellation_controller = InMemoryCancellationController()
        self._shutdown_coordinator = ShutdownCoordinator()
        execution_runner = ExecutionRunner(
            uow_factory=self._uow_factory,
            execution_service=self._execution_service,
            executor=self._executor,
            clock=self._clock,
            claim_coordinator=self._claim_coordinator,
            lease_heartbeat_interval=self._lease_heartbeat_interval,
            cancellation_controller=self._cancellation_controller,
            shutdown_coordinator=self._shutdown_coordinator,
            observer=self._observer,
        )

        self._run_pending_service = RunPendingService(
            clock=self._clock,
            uow_factory=self._uow_factory,
            scheduler_engine=SchedulerEngine(
                uow_factory=self._uow_factory,
                materialization_coordinator=self._materialization_coordinator,
            ),
            concurrency_coordinator=ConcurrencyCoordinator(
                uow_factory=self._uow_factory,
                admission_lock_coordinator=self._admission_lock_coordinator,
                clock=self._clock,
            ),
            execution_runner=execution_runner,
            claim_coordinator=self._claim_coordinator,
            distributed_recovery_service=self._recovery_service,
            shutdown_coordinator=self._shutdown_coordinator,
            observer=self._observer,
        )
        self._runtime = ContinuousSchedulerLoop(
            run_pending_service=self._run_pending_service,
            waiter=EventLoopWaiter(),
            wakeup_planner=WakeUpPlanner(
                clock=self._clock,
                uow_factory=self._uow_factory,
            ),
            clock=self._clock,
            observer=self._observer,
        )

    @property
    def executor_registry(self) -> ExecutorRegistry:
        """Instance-owned registry used for explicit Executor plugin registration."""

        return self._executor_registry

    @property
    def worker_id(self) -> WorkerId:
        """Stable identity used by this Scheduler instance for durable claims."""

        return self._worker_id

    def register_target(
        self,
        reference: str,
        target: Callable[..., object],
    ) -> TargetRef:
        """Register trusted local Python code and return its declarative TargetRef."""

        self._registry.register(reference, target)
        return TargetRef.python(reference)

    def register_async_target(
        self,
        reference: str,
        target: Callable[..., object],
    ) -> TargetRef:
        """Register trusted async Python code and return its declarative TargetRef."""

        self._async_registry.register(reference, target)
        return TargetRef.async_python(reference)

    def register_http_target(
        self,
        reference: str,
        request: HttpRequestSpec,
    ) -> TargetRef:
        """Register a trusted HTTP request and return its opaque declarative TargetRef."""

        self._http_registry.register(reference, request)
        return TargetRef.http(reference)

    def add_schedule(
        self,
        *,
        target: TargetRef | Callable[..., object],
        trigger: Trigger,
        id: str | None = None,
        timezone: Timezone | None = None,
        misfire: MisfirePolicy | None = None,
        concurrency: ConcurrencyPolicy | None = None,
        retry: RetryPolicy | None = None,
        timeout: Duration | None = None,
    ) -> ScheduleId:
        """Create and persist one Schedule using the current Clock reference."""

        schedule_id = ScheduleId(id or uuid4().hex)
        target_ref = self._normalize_target(
            target=target,
            schedule_id=schedule_id,
        )
        local_registration = (
            None
            if isinstance(target, TargetRef)
            else (target_ref.kind, target_ref.reference, target)
        )

        committed = False
        try:
            effective_timezone = self._effective_timezone(
                trigger=trigger,
                timezone=timezone,
            )
            effective_misfire = misfire if misfire is not None else MisfirePolicy.run_now()
            effective_concurrency = (
                concurrency if concurrency is not None else ConcurrencyPolicy.allow()
            )
            effective_retry = retry if retry is not None else RetryPolicy.none()

            schedule = Schedule.create(
                schedule_id=schedule_id,
                definition=ScheduleDefinition(
                    target=target_ref,
                    trigger=trigger,
                    timezone=effective_timezone,
                    misfire=effective_misfire,
                    concurrency=effective_concurrency,
                    retry=effective_retry,
                    timeout=timeout,
                ),
                reference=self._clock.now(),
            )

            with self._uow_factory() as uow:
                uow.schedules.add(schedule)
                uow.commit()
                committed = True
        finally:
            if not committed and local_registration is not None:
                kind, reference, callable_target = local_registration
                if kind == "python_async":
                    self._async_registry.unregister(reference, callable_target)
                else:
                    self._registry.unregister(reference, callable_target)

        self._runtime.wake()
        return schedule.id

    def inspect_schedule(self, schedule_id: ScheduleId | str) -> ScheduleSnapshot:
        """Return an immutable operational snapshot of one Schedule."""

        normalized = schedule_id if isinstance(schedule_id, ScheduleId) else ScheduleId(schedule_id)
        return self._operations.inspect_schedule(normalized)

    def inspect_execution(self, execution_id: ExecutionId | str) -> ExecutionSnapshot:
        """Return an immutable operational snapshot of one Execution."""

        normalized = (
            execution_id if isinstance(execution_id, ExecutionId) else ExecutionId(execution_id)
        )
        return self._operations.inspect_execution(normalized)

    def pause_schedule(self, schedule_id: ScheduleId | str) -> ScheduleSnapshot:
        """Pause future materialization for one Schedule."""

        normalized = schedule_id if isinstance(schedule_id, ScheduleId) else ScheduleId(schedule_id)
        snapshot = self._operations.pause_schedule(normalized)
        self._runtime.wake()
        return snapshot

    def resume_schedule(self, schedule_id: ScheduleId | str) -> ScheduleSnapshot:
        """Resume one paused Schedule from the current Scheduler clock."""

        normalized = schedule_id if isinstance(schedule_id, ScheduleId) else ScheduleId(schedule_id)
        snapshot = self._operations.resume_schedule(normalized)
        self._runtime.wake()
        return snapshot

    def cancel_schedule(self, schedule_id: ScheduleId | str) -> ScheduleSnapshot:
        """Cancel future materialization for one Schedule."""

        normalized = schedule_id if isinstance(schedule_id, ScheduleId) else ScheduleId(schedule_id)
        snapshot = self._operations.cancel_schedule(normalized)
        self._runtime.wake()
        return snapshot

    def health(self) -> SchedulerHealth:
        """Return a non-mutating liveness-oriented health report."""

        persistence_available = self._operations.persistence_available()
        shutdown_requested = self._shutdown_coordinator.is_requested
        return SchedulerHealth(
            healthy=persistence_available,
            worker_id=self._worker_id.value,
            persistence_available=persistence_available,
            runtime_running=self._runtime.is_running,
            shutdown_requested=shutdown_requested,
            active_execution_count=len(self._shutdown_coordinator.snapshot()),
            cycles_completed=self._runtime.cycles_completed,
        )

    def readiness(self) -> SchedulerReadiness:
        """Return whether this Scheduler has crossed its startup safety barriers."""

        persistence_available = self._operations.persistence_available()
        shutdown_requested = self._shutdown_coordinator.is_requested
        ready = (
            persistence_available
            and self._recovery_done
            and self._reconciliation_done
            and not shutdown_requested
        )
        return SchedulerReadiness(
            ready=ready,
            persistence_available=persistence_available,
            recovered=self._recovery_done,
            reconciled=self._reconciliation_done,
            shutdown_requested=shutdown_requested,
        )

    def cancel_execution(self, execution_id: ExecutionId | str) -> ExecutionSnapshot:
        """Request cancellation and return an immutable Execution snapshot."""

        normalized = (
            execution_id if isinstance(execution_id, ExecutionId) else ExecutionId(execution_id)
        )
        execution = self._execution_service.request_cancellation(
            execution_id=normalized,
            requested_at=self._clock.now(),
        )
        if not execution.is_terminal:
            self._cancellation_controller.cancel(normalized.value)
        self._runtime.wake()
        return ExecutionSnapshot.from_execution(execution)

    @property
    def last_recovery_result(self) -> CrashRecoveryResult | None:
        return self._last_recovery_result

    @property
    def last_reconciliation_result(self) -> ReconciliationResult | None:
        return self._last_reconciliation_result

    @property
    def is_running(self) -> bool:
        return self._runtime.is_running

    @property
    def cycles_completed(self) -> int:
        return self._runtime.cycles_completed

    @property
    def last_result(self) -> RunPendingResult | None:
        result = self._runtime.last_result
        return RunPendingResult.from_internal(result) if result is not None else None

    def recover(self, *, limit: int = 1000) -> CrashRecoveryResult:
        """Reconcile persisted orphaned RUNNING Executions before scheduling."""

        if self._runtime.is_running or self._shutdown_coordinator.snapshot():
            raise CrashRecoveryActiveRuntimeError(
                "Crash recovery cannot run while local Executions are active."
            )

        with self._recovery_lock:
            result = self._recovery_service.recover(limit=limit)
            self._last_recovery_result = result
            self._recovery_done = result.complete
            self._reconciliation_done = False
            if not result.complete:
                raise CrashRecoveryIncompleteError(result)
            return result

    def reconcile(self, *, limit: int = 1000) -> ReconciliationResult:
        """Detect and repair deterministic durable graph drift."""

        if self._runtime.is_running or self._shutdown_coordinator.snapshot():
            raise ReconciliationActiveRuntimeError(
                "Reconciliation cannot run while local Executions are active."
            )

        self._ensure_recovered()
        with self._reconciliation_lock:
            result = self._reconciliation_service.reconcile(limit=limit)
            self._last_reconciliation_result = result
            self._reconciliation_done = result.complete
            if not result.complete:
                raise ReconciliationIncompleteError(result)
            return result

    def dispatch_outbox(
        self,
        publisher: OutboxPublisher,
        *,
        limit: int = 100,
    ) -> OutboxDispatchResult:
        """Publish committed outbox messages with at-least-once semantics."""

        dispatcher = OutboxDispatcher(
            clock=self._clock,
            uow_factory=self._uow_factory,
            publisher=publisher,
        )
        return dispatcher.dispatch_pending(limit=limit)

    def cleanup(
        self,
        policy: RetentionPolicy,
        *,
        limit: int = 1000,
    ) -> CleanupResult:
        """Delete bounded immutable history according to an explicit retention policy."""

        return self._retention_service.cleanup(
            policy=policy,
            limit=limit,
        )

    def run_pending(self, *, limit: int = 100) -> RunPendingResult:
        """Run one non-blocking end-to-end scheduling cycle."""

        self._ensure_recovered()
        self._ensure_reconciled()
        result = self._run_pending_service.run_pending(limit=limit)
        return RunPendingResult.from_internal(result)

    def run_forever(
        self,
        *,
        max_sleep: Duration | None = None,
        poll_interval: Duration | None = None,
        limit: int = 100,
    ) -> None:
        """Continuously run with adaptive wake-up bounded by max_sleep."""

        if max_sleep is not None and poll_interval is not None:
            raise PyScheduleKitConfigurationError(
                "Use either max_sleep or poll_interval, not both."
            )

        effective_max_sleep = max_sleep or poll_interval or Duration.seconds(1)
        self._ensure_recovered()
        self._ensure_reconciled()
        self._shutdown_coordinator.reset()
        self._runtime.run_forever(
            max_sleep=effective_max_sleep,
            limit=limit,
        )

    def stop(self) -> None:
        """Request interruption of the continuous scheduler loop."""

        self._runtime.request_stop()

    def shutdown(
        self,
        *,
        mode: ShutdownMode = ShutdownMode.WAIT,
        timeout: Duration | None = None,
    ) -> ShutdownResult:
        """Stop new runtime work and drain or cooperatively cancel active work."""

        self._shutdown_coordinator.request()
        self._runtime.request_stop()
        started = monotonic()

        active = self._shutdown_coordinator.snapshot()
        if mode is ShutdownMode.CANCEL:
            for execution_id in active:
                self._cancellation_controller.cancel(execution_id.value)
                self._persist_running_cancellation(execution_id)

        drained = self._shutdown_coordinator.wait_until_drained(
            timeout=self._remaining_timeout(timeout=timeout, started=started),
        )
        if not drained:
            return ShutdownResult(
                mode=mode,
                completed=False,
                timed_out=True,
                active_execution_ids=self._shutdown_coordinator.snapshot(),
            )

        stopped = self._runtime.wait_until_stopped(
            timeout=self._remaining_timeout(timeout=timeout, started=started),
        )
        completed = drained and stopped
        return ShutdownResult(
            mode=mode,
            completed=completed,
            timed_out=not completed,
            active_execution_ids=self._shutdown_coordinator.snapshot(),
        )

    def _persist_running_cancellation(self, execution_id: ExecutionId) -> None:
        with self._uow_factory() as uow:
            execution = uow.executions.get(execution_id)
        if execution is None or execution.is_terminal:
            return
        if execution.state is not ExecutionState.RUNNING:
            return

        self._execution_service.request_cancellation(
            execution_id=execution_id,
            requested_at=self._clock.now(),
        )

    def _ensure_recovered(self) -> None:
        if self._recovery_done:
            return

        with self._recovery_lock:
            if self._recovery_done:
                return

            result = self._recovery_service.recover()
            self._last_recovery_result = result
            if not result.complete:
                raise CrashRecoveryIncompleteError(result)
            self._recovery_done = True

    def _ensure_reconciled(self) -> None:
        if self._reconciliation_done:
            return

        with self._reconciliation_lock:
            if self._reconciliation_done:
                return

            result = self._reconciliation_service.reconcile()
            self._last_reconciliation_result = result
            if not result.complete:
                raise ReconciliationIncompleteError(result)
            self._reconciliation_done = True

    @staticmethod
    def _remaining_timeout(
        *,
        timeout: Duration | None,
        started: float,
    ) -> Duration | None:
        if timeout is None:
            return None
        remaining = max(0.0, timeout.total_seconds - (monotonic() - started))
        return Duration.seconds(remaining)

    @staticmethod
    def _effective_timezone(
        *,
        trigger: Trigger,
        timezone: Timezone | None,
    ) -> Timezone:
        if isinstance(trigger, CronTrigger):
            if timezone is not None and timezone != trigger.timezone:
                raise ValueError(
                    "Schedule timezone must match CronTrigger timezone when both are provided."
                )
            return trigger.timezone

        return timezone if timezone is not None else Timezone("UTC")

    def _normalize_target(
        self,
        *,
        target: TargetRef | Callable[..., object],
        schedule_id: ScheduleId,
    ) -> TargetRef:
        if isinstance(target, TargetRef):
            return target

        reference = f"local:{schedule_id.value}"
        if inspect.iscoroutinefunction(target):
            self._async_registry.register(reference, target)
            return TargetRef.async_python(reference)

        self._registry.register(reference, target)
        return TargetRef.python(reference)
