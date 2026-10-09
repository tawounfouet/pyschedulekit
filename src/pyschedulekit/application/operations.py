"""Operational inspection and control services for PyScheduleKit."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.application.calendar_resolution import resolve_calendar_binding
from pyschedulekit.application.execution_service import ExecutionNotFoundError
from pyschedulekit.domain.calendar import CalendarSnapshotRef
from pyschedulekit.domain.execution import (
    Execution,
    ExecutionId,
    ExecutionPolicySnapshot,
    ExecutionState,
)
from pyschedulekit.domain.schedule import Schedule, ScheduleId, ScheduleState
from pyschedulekit.domain.time import Instant
from pyschedulekit.errors import PyScheduleKitNotFoundError
from pyschedulekit.ports.calendar import CalendarProvider
from pyschedulekit.ports.persistence import UnitOfWorkFactory
from pyschedulekit.ports.time import Clock


class ScheduleNotFoundError(PyScheduleKitNotFoundError):
    """Raised when an operational Schedule lookup cannot resolve an identity."""


@dataclass(frozen=True, slots=True)
class SchedulerHealth:
    """Liveness-oriented process and persistence health report."""

    healthy: bool
    worker_id: str
    persistence_available: bool
    runtime_running: bool
    shutdown_requested: bool
    active_execution_count: int
    cycles_completed: int


@dataclass(frozen=True, slots=True)
class SchedulerReadiness:
    """Readiness report for accepting scheduling work."""

    ready: bool
    persistence_available: bool
    recovered: bool
    reconciled: bool
    shutdown_requested: bool


@dataclass(frozen=True, slots=True)
class ScheduleSnapshot:
    """Immutable operational view of one Schedule."""

    schedule_id: ScheduleId
    state: ScheduleState
    revision: int
    persistence_version: int
    next_run_time: Instant | None
    target_kind: str
    target_reference: str
    timezone: str
    calendar: CalendarSnapshotRef | None
    timeout_seconds: float | None

    @classmethod
    def from_schedule(cls, schedule: Schedule) -> ScheduleSnapshot:
        timeout = schedule.definition.timeout
        return cls(
            schedule_id=schedule.id,
            state=schedule.state,
            revision=schedule.revision.value,
            persistence_version=schedule.persistence_version.value,
            next_run_time=schedule.next_run_time,
            target_kind=schedule.definition.target.kind,
            target_reference=schedule.definition.target.reference,
            timezone=schedule.definition.timezone.name,
            calendar=schedule.definition.calendar,
            timeout_seconds=timeout.total_seconds if timeout is not None else None,
        )


@dataclass(frozen=True, slots=True)
class ExecutionSnapshot:
    """Immutable operational view of one logical Execution."""

    execution_id: ExecutionId
    request_id: str
    state: ExecutionState
    created_at: Instant
    attempt_count: int
    active_attempt_number: int | None
    next_attempt_at: Instant | None
    cancellation_requested_at: Instant | None
    is_terminal: bool
    target_kind: str
    target_reference: str
    failure_category: str | None
    failure_code: str | None
    completed_at: Instant | None
    policy_snapshot: ExecutionPolicySnapshot

    @property
    def id(self) -> ExecutionId:
        """Compatibility alias matching the domain Execution identity property."""

        return self.execution_id

    @property
    def cancellation_requested(self) -> bool:
        """Whether cooperative cancellation has been requested."""

        return self.cancellation_requested_at is not None

    @classmethod
    def from_execution(cls, execution: Execution) -> ExecutionSnapshot:
        result = execution.result
        return cls(
            execution_id=execution.id,
            request_id=execution.request_id.value,
            state=execution.state,
            created_at=execution.created_at,
            attempt_count=execution.attempt_count,
            active_attempt_number=execution.active_attempt_number,
            next_attempt_at=execution.next_attempt_at,
            cancellation_requested_at=execution.cancellation_requested_at,
            is_terminal=execution.is_terminal,
            target_kind=execution.target.kind,
            target_reference=execution.target.reference,
            failure_category=(
                result.failure.category.value
                if result is not None and result.failure is not None
                else None
            ),
            failure_code=(
                result.failure.code if result is not None and result.failure is not None else None
            ),
            completed_at=result.completed_at if result is not None else None,
            policy_snapshot=execution.policy_snapshot,
        )


class SchedulerOperations:
    """Operational boundary over durable Schedule and Execution state."""

    def __init__(
        self,
        *,
        clock: Clock,
        uow_factory: UnitOfWorkFactory,
        calendar_provider: CalendarProvider | None = None,
    ) -> None:
        self._clock = clock
        self._uow_factory = uow_factory
        self._calendar_provider = calendar_provider

    def inspect_schedule(self, schedule_id: ScheduleId) -> ScheduleSnapshot:
        with self._uow_factory() as uow:
            schedule = uow.schedules.get(schedule_id)
            if schedule is None:
                raise ScheduleNotFoundError(schedule_id.value)
            return ScheduleSnapshot.from_schedule(schedule)

    def inspect_execution(self, execution_id: ExecutionId) -> ExecutionSnapshot:
        with self._uow_factory() as uow:
            execution = uow.executions.get(execution_id)
            if execution is None:
                raise ExecutionNotFoundError(execution_id.value)
            return ExecutionSnapshot.from_execution(execution)

    def pause_schedule(self, schedule_id: ScheduleId) -> ScheduleSnapshot:
        with self._uow_factory() as uow:
            schedule = uow.schedules.get(schedule_id)
            if schedule is None:
                raise ScheduleNotFoundError(schedule_id.value)
            schedule.pause()
            uow.schedules.save(schedule)
            uow.commit()
            return ScheduleSnapshot.from_schedule(schedule)

    def resume_schedule(self, schedule_id: ScheduleId) -> ScheduleSnapshot:
        reference = self._clock.now()
        with self._uow_factory() as uow:
            schedule = uow.schedules.get(schedule_id)
            if schedule is None:
                raise ScheduleNotFoundError(schedule_id.value)
            calendar = resolve_calendar_binding(
                schedule.definition.calendar,
                self._calendar_provider,
            )
            schedule.resume(reference=reference, calendar=calendar)
            uow.schedules.save(schedule)
            uow.commit()
            return ScheduleSnapshot.from_schedule(schedule)

    def cancel_schedule(self, schedule_id: ScheduleId) -> ScheduleSnapshot:
        with self._uow_factory() as uow:
            schedule = uow.schedules.get(schedule_id)
            if schedule is None:
                raise ScheduleNotFoundError(schedule_id.value)
            schedule.cancel()
            uow.schedules.save(schedule)
            uow.commit()
            return ScheduleSnapshot.from_schedule(schedule)

    def persistence_available(self) -> bool:
        """Probe the persistence boundary without mutating durable state."""

        try:
            with self._uow_factory() as uow:
                uow.schedules.next_run_time()
        except Exception:
            return False
        return True
