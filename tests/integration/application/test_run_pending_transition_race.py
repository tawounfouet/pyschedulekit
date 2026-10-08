"""POST-00B regression test for cancellation between listing and Attempt start."""

from datetime import UTC, datetime

from pyschedulekit.application.claims import ExecutionClaimCoordinator
from pyschedulekit.application.concurrency import ConcurrencyCoordinator
from pyschedulekit.application.execution_runner import ExecutionRunner, ExecutionRunResult
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.application.run_pending import RunPendingService
from pyschedulekit.application.scheduler_engine import SchedulerEngine
from pyschedulekit.domain.claim import ExecutionClaimHandle, ExecutionClaimState, WorkerId
from pyschedulekit.domain.execution import ExecutionId, ExecutionState
from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.schedule import ScheduleId, ScheduleRevision, TargetRef
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.infrastructure.local_executor import LocalExecutor, PythonTargetRegistry
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


class CancelBeforeStartRunner:
    """Force the race after run_pending listed the Execution but before start_attempt."""

    def __init__(
        self,
        *,
        execution_service: ExecutionService,
        inner: ExecutionRunner,
        clock: MutableClock,
    ) -> None:
        self._execution_service = execution_service
        self._inner = inner
        self._clock = clock

    def run(
        self,
        *,
        execution_id: ExecutionId,
        claim_handle: ExecutionClaimHandle | None = None,
    ) -> ExecutionRunResult:
        self._execution_service.request_cancellation(
            execution_id=execution_id,
            requested_at=self._clock.now(),
        )
        return self._inner.run(
            execution_id=execution_id,
            claim_handle=claim_handle,
        )


def test_run_pending_survives_cancel_between_listing_and_attempt_start() -> None:
    factory = InMemoryUnitOfWorkFactory()
    clock = MutableClock(_instant())
    registry = PythonTargetRegistry()
    registry.register("refresh", lambda: None)

    request = ExecutionRequest(
        id=RequestId("request-transition-race"),
        occurrence_key=OccurrenceKey(
            schedule_id=ScheduleId("schedule-transition-race"),
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
    claim_coordinator = ExecutionClaimCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-a"),
        ttl=Duration.seconds(30),
    )
    inner_runner = ExecutionRunner(
        uow_factory=factory,
        execution_service=execution_service,
        executor=LocalExecutor(registry=registry, clock=clock),
        clock=clock,
    )
    runner = CancelBeforeStartRunner(
        execution_service=execution_service,
        inner=inner_runner,
        clock=clock,
    )
    service = RunPendingService(
        clock=clock,
        uow_factory=factory,
        scheduler_engine=SchedulerEngine(uow_factory=factory),
        concurrency_coordinator=ConcurrencyCoordinator(uow_factory=factory),
        execution_runner=runner,
        claim_coordinator=claim_coordinator,
    )

    result = service.run_pending()

    execution_id = ExecutionId.for_request(request.id)
    assert result.executions == ()
    assert result.claim_denied_execution_ids == ()
    assert len(result.errors) == 1
    assert result.errors[0].request_id == request.id
    assert result.errors[0].code == "execution.transition"

    with factory() as uow:
        execution = uow.executions.get(execution_id)
        claim = uow.claims.get(execution_id)

    assert execution is not None
    assert execution.state is ExecutionState.CANCELLED
    assert claim is not None
    assert claim.state is ExecutionClaimState.RELEASED
