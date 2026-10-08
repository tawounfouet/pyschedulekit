"""LOT-17 integration tests for cancellation control-plane behavior."""

from datetime import UTC, datetime
from threading import Event, Thread
from time import sleep

from pyschedulekit.application.execution_runner import ExecutionRunner, ExecutionRunResult
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.domain.execution import (
    AttemptState,
    Execution,
    ExecutionState,
    FailureCategory,
)
from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.retry import RetryPolicy
from pyschedulekit.domain.schedule import ScheduleId, ScheduleRevision, TargetRef
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.infrastructure.cancellation import InMemoryCancellationController
from pyschedulekit.infrastructure.local_executor import LocalExecutor, PythonTargetRegistry
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.ports.cancellation import CancellationToken
from pyschedulekit.testing import MutableClock


def _instant(second: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, second, tzinfo=UTC))


def _dispatch(
    factory: InMemoryUnitOfWorkFactory,
    *,
    retry: RetryPolicy | None = None,
    timeout: Duration | None = None,
) -> tuple[ExecutionService, Execution]:
    request = ExecutionRequest(
        id=RequestId("request-cancellation"),
        occurrence_key=OccurrenceKey(
            schedule_id=ScheduleId("schedule-cancellation"),
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        ),
        target=TargetRef.python("cancel-target"),
        created_at=_instant(),
        retry_policy=retry,
        timeout=timeout,
    )
    with factory() as uow:
        uow.requests.add(request)
        uow.commit()

    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(
        request_id=request.id,
        created_at=_instant(),
    )
    return service, execution


def test_t_cancel_run_001_queued_execution_cancels_without_attempt() -> None:
    factory = InMemoryUnitOfWorkFactory()
    service, execution = _dispatch(factory)

    cancelled = service.request_cancellation(
        execution_id=execution.id,
        requested_at=_instant(1),
    )

    assert cancelled.state is ExecutionState.CANCELLED
    assert cancelled.attempt_count == 0

    with factory() as uow:
        assert uow.attempts.list_for_execution(execution.id) == []
        assert uow.executions.list_runnable(now=_instant(2), limit=10) == []


def test_t_cancel_run_002_running_cooperative_target_cancels_without_retry() -> None:
    factory = InMemoryUnitOfWorkFactory()
    service, execution = _dispatch(
        factory,
        retry=RetryPolicy(max_attempts=3),
    )
    clock = MutableClock(_instant())
    registry = PythonTargetRegistry()
    controller = InMemoryCancellationController()
    started = Event()
    result_box: list[ExecutionRunResult] = []

    def target(cancellation_token: CancellationToken) -> None:
        started.set()
        while not cancellation_token.is_cancelled:
            sleep(0.001)
        cancellation_token.raise_if_cancelled()

    registry.register("cancel-target", target)
    runner = ExecutionRunner(
        uow_factory=factory,
        execution_service=service,
        executor=LocalExecutor(registry=registry, clock=clock),
        clock=clock,
        cancellation_controller=controller,
    )

    worker = Thread(
        target=lambda: result_box.append(runner.run(execution_id=execution.id)),
    )
    worker.start()
    assert started.wait(1)

    requested = service.request_cancellation(
        execution_id=execution.id,
        requested_at=_instant(1),
    )
    controller.cancel(execution.id.value)
    worker.join(1)

    assert not worker.is_alive()
    assert requested.cancellation_requested
    assert len(result_box) == 1
    result = result_box[0]
    assert result.execution.state is ExecutionState.CANCELLED
    assert result.retry_decision is None
    assert result.outcome.failure is not None
    assert result.outcome.failure.retryable_hint is False

    with factory() as uow:
        attempts = uow.attempts.list_for_execution(execution.id)
        assert [attempt.state for attempt in attempts] == [AttemptState.CANCELLED]


def test_t_cancel_run_003_retry_wait_cancellation_prevents_next_attempt() -> None:
    factory = InMemoryUnitOfWorkFactory()
    retry = RetryPolicy(max_attempts=3)
    service, execution = _dispatch(factory, retry=retry)
    clock = MutableClock(_instant())
    registry = PythonTargetRegistry()
    controller = InMemoryCancellationController()

    def target() -> None:
        raise RuntimeError("temporary")

    registry.register("cancel-target", target)
    runner = ExecutionRunner(
        uow_factory=factory,
        execution_service=service,
        executor=LocalExecutor(registry=registry, clock=clock),
        clock=clock,
        cancellation_controller=controller,
    )

    first = runner.run(execution_id=execution.id)
    assert first.execution.state is ExecutionState.RETRY_WAIT

    cancelled = service.request_cancellation(
        execution_id=execution.id,
        requested_at=_instant(1),
    )

    assert cancelled.state is ExecutionState.CANCELLED
    assert cancelled.attempt_count == 1
    with factory() as uow:
        assert uow.executions.list_runnable(now=_instant(2), limit=10) == []


def test_t_cancel_run_004_non_cooperative_timeout_is_cancelled_without_retry() -> None:
    """LOT-17: cancellation wins over retry even through the timeout path."""

    factory = InMemoryUnitOfWorkFactory()
    service, execution = _dispatch(
        factory,
        retry=RetryPolicy(max_attempts=3),
        timeout=Duration.seconds(0.1),
    )
    clock = MutableClock(_instant())
    registry = PythonTargetRegistry()
    controller = InMemoryCancellationController()
    started = Event()
    release = Event()
    result_box: list[ExecutionRunResult] = []

    def target(cancellation_token: CancellationToken) -> None:
        del cancellation_token
        started.set()
        release.wait(1)  # ignores cancellation on purpose

    registry.register("cancel-target", target)
    runner = ExecutionRunner(
        uow_factory=factory,
        execution_service=service,
        executor=LocalExecutor(registry=registry, clock=clock),
        clock=clock,
        cancellation_controller=controller,
    )

    worker = Thread(
        target=lambda: result_box.append(runner.run(execution_id=execution.id)),
    )
    worker.start()
    assert started.wait(1)

    requested = service.request_cancellation(
        execution_id=execution.id,
        requested_at=_instant(1),
    )
    controller.cancel(execution.id.value)
    worker.join(2)
    release.set()

    assert not worker.is_alive()
    assert requested.cancellation_requested
    assert len(result_box) == 1
    result = result_box[0]
    assert result.execution.state is ExecutionState.CANCELLED
    assert result.retry_decision is None
    assert result.outcome.failure is not None
    assert result.outcome.failure.category is FailureCategory.CANCELLED

    with factory() as uow:
        attempts = uow.attempts.list_for_execution(execution.id)
        assert [attempt.state for attempt in attempts] == [AttemptState.CANCELLED]
        assert uow.executions.list_runnable(now=_instant(2), limit=10) == []
