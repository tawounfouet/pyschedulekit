"""Public Scheduler facade for the first in-memory vertical slice."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from pyschedulekit.application.execution_runner import ExecutionRunner
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.application.run_pending import RunPendingResult, RunPendingService
from pyschedulekit.application.scheduler_engine import SchedulerEngine
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    TargetRef,
)
from pyschedulekit.domain.time import Timezone
from pyschedulekit.domain.trigger import Trigger
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
        self._clock = clock or SystemClock()
        self._uow_factory = uow_factory or InMemoryUnitOfWorkFactory()
        self._registry = registry or PythonTargetRegistry()

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
            scheduler_engine=SchedulerEngine(uow_factory=self._uow_factory),
            execution_service=execution_service,
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
    ) -> ScheduleId:
        """Create and persist one Schedule using the current Clock reference."""

        schedule_id = ScheduleId(id or uuid4().hex)
        target_ref = self._normalize_target(
            target=target,
            schedule_id=schedule_id,
        )

        schedule = Schedule.create(
            schedule_id=schedule_id,
            definition=ScheduleDefinition(
                target=target_ref,
                trigger=trigger,
                timezone=timezone or Timezone("UTC"),
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
