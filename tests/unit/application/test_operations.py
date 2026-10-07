"""LOT-31 unit tests for the operational service boundary."""

from datetime import UTC, datetime

import pytest

from pyschedulekit.application.execution_service import ExecutionNotFoundError
from pyschedulekit.application.operations import (
    ScheduleNotFoundError,
    SchedulerOperations,
)
from pyschedulekit.domain.execution import ExecutionId
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleState,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.testing import MutableClock


def _instant(minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, minute, tzinfo=UTC))


def _schedule() -> Schedule:
    return Schedule.create(
        schedule_id=ScheduleId("schedule-1"),
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:refresh"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(10),
            ),
        ),
        reference=_instant(),
    )


def _service() -> tuple[SchedulerOperations, InMemoryUnitOfWorkFactory, MutableClock]:
    factory = InMemoryUnitOfWorkFactory()
    clock = MutableClock(_instant())
    with factory() as uow:
        uow.schedules.add(_schedule())
        uow.commit()
    return SchedulerOperations(clock=clock, uow_factory=factory), factory, clock


def test_t_operations_unit_001_inspect_schedule_returns_immutable_snapshot() -> None:
    service, _, _ = _service()

    snapshot = service.inspect_schedule(ScheduleId("schedule-1"))

    assert snapshot.schedule_id == ScheduleId("schedule-1")
    assert snapshot.state is ScheduleState.ACTIVE
    assert snapshot.next_run_time == _instant(10)
    assert snapshot.target_reference == "jobs:refresh"


def test_t_operations_unit_002_pause_and_resume_use_explicit_clock_reference() -> None:
    service, _, clock = _service()

    paused = service.pause_schedule(ScheduleId("schedule-1"))
    assert paused.state is ScheduleState.PAUSED
    assert paused.next_run_time is None

    clock.set(_instant(25))
    resumed = service.resume_schedule(ScheduleId("schedule-1"))

    assert resumed.state is ScheduleState.ACTIVE
    assert resumed.next_run_time == _instant(30)


def test_t_operations_unit_003_cancel_schedule_is_persisted() -> None:
    service, factory, _ = _service()

    cancelled = service.cancel_schedule(ScheduleId("schedule-1"))

    assert cancelled.state is ScheduleState.CANCELLED
    with factory() as uow:
        loaded = uow.schedules.get(ScheduleId("schedule-1"))
        assert loaded is not None
        assert loaded.state is ScheduleState.CANCELLED


def test_t_operations_unit_004_missing_resources_fail_explicitly() -> None:
    service, _, _ = _service()

    with pytest.raises(ScheduleNotFoundError):
        service.inspect_schedule(ScheduleId("missing"))

    with pytest.raises(ExecutionNotFoundError):
        service.inspect_execution(ExecutionId("missing"))


def test_t_operations_unit_005_persistence_probe_is_non_mutating() -> None:
    service, factory, _ = _service()

    assert service.persistence_available() is True

    with factory() as uow:
        loaded = uow.schedules.get(ScheduleId("schedule-1"))
        assert loaded is not None
        assert loaded.persistence_version.value == 0
