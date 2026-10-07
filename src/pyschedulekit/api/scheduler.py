"""Public Scheduler facade for the first in-memory vertical slice."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from pyschedulekit.application.concurrency import ConcurrencyCoordinator
from pyschedulekit.application.execution_runner import ExecutionRunner
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.application.run_pending import RunPendingResult, RunPendingService
from pyschedulekit.application.scheduler_engine import SchedulerEngine
from pyschedulekit.domain.concurrency import ConcurrencyPolicy
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
from pyschedulekit.infrastructure.local_executor import (
    LocalExecutor,
    PythonTargetRegistry,
)
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
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

        execution_service = ExecutionService(uow_factory=self._uow_factory)
        execution_runner = ExecutionRunner(
            uow_factory=self._uow_factory,
            execution_service=execution_service,
            executor=LocalExecutor(
                registry=self._registry,
                clock=self._clock,
            ),
            clock=self._clock,
        )

        self._run_pending_service = RunPendingService(
            clock=self._clock,
            uow_factory=self._uow_factory,
            scheduler_engine=SchedulerEngine(uow_factory=self._uow_factory),
            concurrency_coordinator=ConcurrencyCoordinator(uow_factory=self._uow_factory),
            execution_runner=execution_runner,
        )

    def register_target(
        self,
        reference: str,
        target: Callable[[], object],
    ) -> TargetRef:
        """Register trusted local Python code and return its declarative TargetRef."""

        self._registry.register(reference, target)
        return TargetRef.python(reference)

    def add_schedule(
        self,
        *,
        target: TargetRef | Callable[[], object],
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

        return schedule.id

    def run_pending(self, *, limit: int = 100) -> RunPendingResult:
        """Run one non-blocking end-to-end scheduling cycle."""

        return self._run_pending_service.run_pending(limit=limit)

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
        target: TargetRef | Callable[[], object],
        schedule_id: ScheduleId,
    ) -> TargetRef:
        if isinstance(target, TargetRef):
            return target

        reference = f"local:{schedule_id.value}"
        self._registry.register(reference, target)
        return TargetRef.python(reference)
