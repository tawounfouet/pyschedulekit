"""LOT-11 integration tests for durable work resumption."""

from datetime import UTC, datetime

from pyschedulekit.application.concurrency import ConcurrencyCoordinator
from pyschedulekit.application.execution_runner import ExecutionRunner
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.application.run_pending import RunPendingService
from pyschedulekit.application.scheduler_engine import SchedulerEngine
from pyschedulekit.domain.execution import ExecutionState
from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.schedule import ScheduleId, ScheduleRevision, TargetRef
from pyschedulekit.domain.time import Instant
from pyschedulekit.infrastructure.local_executor import LocalExecutor, PythonTargetRegistry
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def test_pending_request_from_previous_process_is_dispatched_and_executed() -> None:
    factory = InMemoryUnitOfWorkFactory()
    clock = MutableClock(_instant())
    registry = PythonTargetRegistry()
    calls: list[str] = []
    registry.register("refresh", lambda: calls.append("called"))

    request = ExecutionRequest(
        id=RequestId("request-1"),
        occurrence_key=OccurrenceKey(
            schedule_id=ScheduleId("schedule-1"),
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(hour=9, minute=50),
        ),
        target=TargetRef.python("refresh"),
        created_at=_instant(hour=9, minute=50),
    )

    with factory() as uow:
        uow.requests.add(request)
        uow.commit()

    execution_service = ExecutionService(uow_factory=factory)
    runner = ExecutionRunner(
        uow_factory=factory,
        execution_service=execution_service,
        executor=LocalExecutor(registry=registry, clock=clock),
        clock=clock,
    )
    service = RunPendingService(
        clock=clock,
        uow_factory=factory,
        scheduler_engine=SchedulerEngine(uow_factory=factory),
        concurrency_coordinator=ConcurrencyCoordinator(uow_factory=factory),
        execution_runner=runner,
    )

    result = service.run_pending()

    assert result.materialized_request_ids == ()
    assert calls == ["called"]
    assert len(result.executions) == 1
    assert result.executions[0].execution.state is ExecutionState.SUCCESS
    assert result.errors == ()
