"""LOT-28 integration test for the execution lease heartbeat."""

from time import monotonic, sleep

from pyschedulekit.application.claims import ExecutionClaimCoordinator
from pyschedulekit.application.execution_runner import ExecutionRunner
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.domain.claim import ExecutionClaimState, WorkerId
from pyschedulekit.domain.execution import ExecutionState
from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.schedule import ScheduleId, ScheduleRevision, TargetRef
from pyschedulekit.domain.time import Duration
from pyschedulekit.infrastructure.local_executor import LocalExecutor, PythonTargetRegistry
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.testing import add_request_with_parent
from pyschedulekit.infrastructure.time import SystemClock


def test_t_lease_heartbeat_001_renews_during_long_running_callable() -> None:
    factory = InMemoryUnitOfWorkFactory()
    clock = SystemClock()
    created_at = clock.now()
    request = ExecutionRequest(
        id=RequestId("lease-heartbeat"),
        occurrence_key=OccurrenceKey(
            schedule_id=ScheduleId("lease-heartbeat"),
            schedule_revision=ScheduleRevision(1),
            scheduled_at=created_at,
        ),
        target=TargetRef.python("lease-heartbeat"),
        created_at=created_at,
    )
    with factory() as uow:
        add_request_with_parent(uow=uow, request=request)
        uow.commit()

    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(
        request_id=request.id,
        created_at=created_at,
    )
    coordinator = ExecutionClaimCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("worker-a"),
        ttl=Duration.seconds(0.30),
    )
    acquired = coordinator.acquire(
        execution_id=execution.id,
        now=clock.now(),
    )
    assert acquired.handle is not None
    original_expiry = acquired.handle.expires_at

    registry = PythonTargetRegistry()
    observed_fencing: list[int] = []

    def target(fencing_token: int) -> None:
        observed_fencing.append(fencing_token)
        deadline = monotonic() + 1.0
        while monotonic() < deadline:
            with factory() as uow:
                claim = uow.claims.get(execution.id)
                assert claim is not None
                if claim.expires_at > original_expiry:
                    return
            sleep(0.01)
        raise AssertionError("lease heartbeat did not renew the execution lease")

    registry.register("lease-heartbeat", target)
    runner = ExecutionRunner(
        uow_factory=factory,
        execution_service=service,
        executor=LocalExecutor(registry=registry, clock=clock),
        clock=clock,
        claim_coordinator=coordinator,
        lease_heartbeat_interval=Duration.seconds(0.05),
    )

    result = runner.run(
        execution_id=execution.id,
        claim_handle=acquired.handle,
    )

    assert result.execution.state is ExecutionState.SUCCESS
    assert observed_fencing == [acquired.handle.generation]

    with factory() as uow:
        claim = uow.claims.get(execution.id)
        assert claim is not None
        assert claim.state is ExecutionClaimState.RELEASED
        assert claim.generation == acquired.handle.generation
        assert claim.expires_at > original_expiry
