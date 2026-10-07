"""Public Scheduler facade for the first in-memory vertical slice."""

from __future__ import annotations

from collections.abc import Callable
from time import monotonic
from uuid import uuid4

from pyschedulekit.application.concurrency import ConcurrencyCoordinator
from pyschedulekit.application.execution_runner import ExecutionRunner
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.application.run_pending import RunPendingResult, RunPendingService
from pyschedulekit.application.runtime import ContinuousSchedulerLoop
from pyschedulekit.application.scheduler_engine import SchedulerEngine
from pyschedulekit.application.shutdown import (
    ShutdownCoordinator,
    ShutdownMode,
    ShutdownResult,
)
from pyschedulekit.application.wakeup import WakeUpPlanner
from pyschedulekit.domain.concurrency import ConcurrencyPolicy
from pyschedulekit.domain.execution import Execution, ExecutionId
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
from pyschedulekit.infrastructure.cancellation import InMemoryCancellationController
from pyschedulekit.infrastructure.local_executor import (
    LocalExecutor,
    PythonTargetRegistry,
)
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.infrastructure.runtime import EventLoopWaiter
from pyschedulekit.infrastructure.time import SystemClock
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
    ) -> None:
        self._clock: Clock = clock if clock is not None else SystemClock()
        self._uow_factory: UnitOfWorkFactory = (
            uow_factory if uow_factory is not None else InMemoryUnitOfWorkFactory()
        )
        self._registry = registry if registry is not None else PythonTargetRegistry()

        self._execution_service = ExecutionService(uow_factory=self._uow_factory)
        self._cancellation_controller = InMemoryCancellationController()
        self._shutdown_coordinator = ShutdownCoordinator()
        execution_runner = ExecutionRunner(
            uow_factory=self._uow_factory,
            execution_service=self._execution_service,
            executor=LocalExecutor(
                registry=self._registry,
                clock=self._clock,
            ),
            clock=self._clock,
            cancellation_controller=self._cancellation_controller,
            shutdown_coordinator=self._shutdown_coordinator,
        )

        self._run_pending_service = RunPendingService(
            clock=self._clock,
            uow_factory=self._uow_factory,
            scheduler_engine=SchedulerEngine(uow_factory=self._uow_factory),
            concurrency_coordinator=ConcurrencyCoordinator(uow_factory=self._uow_factory),
            execution_runner=execution_runner,
            shutdown_coordinator=self._shutdown_coordinator,
        )
        self._runtime = ContinuousSchedulerLoop(
            run_pending_service=self._run_pending_service,
            waiter=EventLoopWaiter(),
            wakeup_planner=WakeUpPlanner(
                clock=self._clock,
                uow_factory=self._uow_factory,
            ),
        )

    def register_target(
        self,
        reference: str,
        target: Callable[..., object],
    ) -> TargetRef:
        """Register trusted local Python code and return its declarative TargetRef."""

        self._registry.register(reference, target)
        return TargetRef.python(reference)

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

        self._runtime.wake()
        return schedule.id

    def cancel_execution(self, execution_id: ExecutionId | str) -> Execution:
        """Request cancellation of one logical Execution."""

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
        return execution

    @property
    def is_running(self) -> bool:
        return self._runtime.is_running

    @property
    def cycles_completed(self) -> int:
        return self._runtime.cycles_completed

    @property
    def last_result(self) -> RunPendingResult | None:
        return self._runtime.last_result

    def run_pending(self, *, limit: int = 100) -> RunPendingResult:
        """Run one non-blocking end-to-end scheduling cycle."""

        return self._run_pending_service.run_pending(limit=limit)

    def run_forever(
        self,
        *,
        max_sleep: Duration | None = None,
        poll_interval: Duration | None = None,
        limit: int = 100,
    ) -> None:
        """Continuously run with adaptive wake-up bounded by max_sleep."""

        if max_sleep is not None and poll_interval is not None:
            raise ValueError("Use either max_sleep or poll_interval, not both.")

        effective_max_sleep = max_sleep or poll_interval or Duration.seconds(1)
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
        if execution.state.value != "running":
            return

        self._execution_service.request_cancellation(
            execution_id=execution_id,
            requested_at=self._clock.now(),
        )

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
        self._registry.register(reference, target)
        return TargetRef.python(reference)
