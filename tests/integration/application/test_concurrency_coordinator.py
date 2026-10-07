"""LOT-14 integration tests for concurrency admission coordination."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from pyschedulekit.application.concurrency import ConcurrencyCoordinator
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.domain.concurrency import (
    ConcurrencyDecisionAction,
    ConcurrencyOverflowPolicy,
    ConcurrencyPolicy,
)
from pyschedulekit.domain.execution import ExecutionState
from pyschedulekit.domain.execution_request import (
    ExecutionRequest,
    ExecutionRequestState,
    RequestId,
)
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.schedule import ScheduleId, ScheduleRevision, TargetRef
from pyschedulekit.domain.time import Instant
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory


def _instant(minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, minute, tzinfo=UTC))


def _request(
    *,
    request_id: str,
    schedule_id: str = "schedule-1",
    minute: int = 0,
    policy: ConcurrencyPolicy | None = None,
) -> ExecutionRequest:
    return ExecutionRequest(
        id=RequestId(request_id),
        occurrence_key=OccurrenceKey(
            schedule_id=ScheduleId(schedule_id),
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(minute),
        ),
        target=TargetRef.python("refresh"),
        created_at=_instant(minute),
        concurrency_policy=policy or ConcurrencyPolicy.allow(),
    )


def _persist(
    factory: InMemoryUnitOfWorkFactory,
    *requests: ExecutionRequest,
) -> None:
    with factory() as uow:
        for request in requests:
            uow.requests.add(request)
        uow.commit()


def test_t_con_020_limit_reserves_slot_when_execution_is_queued() -> None:
    factory = InMemoryUnitOfWorkFactory()
    policy = ConcurrencyPolicy.limit(max_instances=1)
    first = _request(request_id="request-1", policy=policy)
    second = _request(request_id="request-2", minute=1, policy=policy)
    _persist(factory, first, second)
    coordinator = ConcurrencyCoordinator(uow_factory=factory)

    admitted = coordinator.admit(request_id=first.id, created_at=_instant())
    queued = coordinator.admit(request_id=second.id, created_at=_instant(minute=1))

    assert admitted.action is ConcurrencyDecisionAction.ADMIT
    assert admitted.execution is not None
    assert admitted.execution.state is ExecutionState.QUEUED
    assert queued.action is ConcurrencyDecisionAction.QUEUE
    assert queued.execution is None

    with factory() as uow:
        persisted_second = uow.requests.get(second.id)
        assert persisted_second is not None
        assert persisted_second.state is ExecutionRequestState.WAITING_ADMISSION
        assert uow.executions.get_by_request(second.id) is None


def test_t_con_021_terminal_execution_releases_slot_for_waiting_request() -> None:
    factory = InMemoryUnitOfWorkFactory()
    policy = ConcurrencyPolicy.limit(max_instances=1)
    first = _request(request_id="request-1", policy=policy)
    second = _request(request_id="request-2", minute=1, policy=policy)
    _persist(factory, first, second)
    coordinator = ConcurrencyCoordinator(uow_factory=factory)
    service = ExecutionService(uow_factory=factory)

    admitted = coordinator.admit(request_id=first.id, created_at=_instant())
    assert admitted.execution is not None
    coordinator.admit(request_id=second.id, created_at=_instant(minute=1))

    attempt = service.start_attempt(
        execution_id=admitted.execution.id,
        started_at=_instant(minute=2),
    )
    service.succeed_attempt(
        attempt_id=attempt.id,
        completed_at=_instant(minute=3),
    )

    retried = coordinator.admit(
        request_id=second.id,
        created_at=_instant(minute=4),
    )

    assert retried.action is ConcurrencyDecisionAction.ADMIT
    assert retried.execution is not None

    with factory() as uow:
        persisted_second = uow.requests.get(second.id)
        assert persisted_second is not None
        assert persisted_second.state is ExecutionRequestState.DISPATCHED


def test_t_con_022_retry_wait_still_consumes_concurrency_slot() -> None:
    from pyschedulekit.domain.execution import Failure, FailureCategory

    factory = InMemoryUnitOfWorkFactory()
    policy = ConcurrencyPolicy.limit(max_instances=1)
    first = _request(request_id="request-1", policy=policy)
    second = _request(request_id="request-2", minute=1, policy=policy)
    _persist(factory, first, second)
    coordinator = ConcurrencyCoordinator(uow_factory=factory)
    service = ExecutionService(uow_factory=factory)

    admitted = coordinator.admit(request_id=first.id, created_at=_instant())
    assert admitted.execution is not None
    attempt = service.start_attempt(
        execution_id=admitted.execution.id,
        started_at=_instant(minute=1),
    )
    service.fail_attempt(
        attempt_id=attempt.id,
        failure=Failure(
            category=FailureCategory.TRANSIENT,
            code="temporary",
            message="Temporary failure.",
            occurred_at=_instant(minute=2),
            retryable_hint=True,
        ),
        completed_at=_instant(minute=2),
        retry_at=_instant(minute=10),
    )

    queued = coordinator.admit(
        request_id=second.id,
        created_at=_instant(minute=3),
    )

    assert queued.action is ConcurrencyDecisionAction.QUEUE


def test_t_con_023_drop_marks_request_terminal_without_execution() -> None:
    factory = InMemoryUnitOfWorkFactory()
    policy = ConcurrencyPolicy.limit(
        max_instances=1,
        overflow=ConcurrencyOverflowPolicy.DROP,
    )
    first = _request(request_id="request-1", policy=policy)
    second = _request(request_id="request-2", minute=1, policy=policy)
    _persist(factory, first, second)
    coordinator = ConcurrencyCoordinator(uow_factory=factory)

    coordinator.admit(request_id=first.id, created_at=_instant())
    dropped = coordinator.admit(
        request_id=second.id,
        created_at=_instant(minute=1),
    )

    assert dropped.action is ConcurrencyDecisionAction.DROP
    assert dropped.execution is None

    with factory() as uow:
        persisted = uow.requests.get(second.id)
        assert persisted is not None
        assert persisted.state is ExecutionRequestState.DROPPED
        assert uow.executions.get_by_request(second.id) is None


def test_t_con_024_concurrency_scope_is_per_schedule() -> None:
    factory = InMemoryUnitOfWorkFactory()
    policy = ConcurrencyPolicy.limit(max_instances=1)
    a = _request(request_id="request-a", schedule_id="schedule-a", policy=policy)
    b = _request(request_id="request-b", schedule_id="schedule-b", policy=policy)
    _persist(factory, a, b)
    coordinator = ConcurrencyCoordinator(uow_factory=factory)

    first = coordinator.admit(request_id=a.id, created_at=_instant())
    second = coordinator.admit(request_id=b.id, created_at=_instant())

    assert first.action is ConcurrencyDecisionAction.ADMIT
    assert second.action is ConcurrencyDecisionAction.ADMIT


def test_t_con_025_allow_policy_does_not_limit_non_terminal_executions() -> None:
    factory = InMemoryUnitOfWorkFactory()
    first = _request(request_id="request-1")
    second = _request(request_id="request-2", minute=1)
    _persist(factory, first, second)
    coordinator = ConcurrencyCoordinator(uow_factory=factory)

    one = coordinator.admit(request_id=first.id, created_at=_instant())
    two = coordinator.admit(request_id=second.id, created_at=_instant(minute=1))

    assert one.action is ConcurrencyDecisionAction.ADMIT
    assert two.action is ConcurrencyDecisionAction.ADMIT


def test_t_con_026_same_coordinator_serializes_competing_admissions() -> None:
    factory = InMemoryUnitOfWorkFactory()
    policy = ConcurrencyPolicy.limit(max_instances=1)
    first = _request(request_id="request-1", policy=policy)
    second = _request(request_id="request-2", minute=1, policy=policy)
    _persist(factory, first, second)
    coordinator = ConcurrencyCoordinator(uow_factory=factory)

    def admit(request: ExecutionRequest) -> ConcurrencyDecisionAction:
        return coordinator.admit(
            request_id=request.id,
            created_at=_instant(minute=2),
        ).action

    with ThreadPoolExecutor(max_workers=2) as pool:
        actions = list(pool.map(admit, (first, second)))

    assert sorted(action.value for action in actions) == ["admit", "queue"]

    with factory() as uow:
        assert uow.executions.count_non_terminal_for_schedule(ScheduleId("schedule-1")) == 1
