"""LOT-15 integration tests for retry execution lifecycle."""

from datetime import UTC, datetime

from pyschedulekit.application.execution_runner import ExecutionRunner
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.domain.execution import ExecutionPolicySnapshot, ExecutionState
from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.retry import FixedBackoff, RetryDecisionReason, RetryPolicy
from pyschedulekit.domain.schedule import ScheduleId, ScheduleRevision, TargetRef
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.infrastructure.local_executor import LocalExecutor, PythonTargetRegistry
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.testing import MutableClock


def _instant(minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, minute, tzinfo=UTC))


def _dispatch(
    factory: InMemoryUnitOfWorkFactory,
    *,
    retry: RetryPolicy,
):
    request = ExecutionRequest(
        id=RequestId("request-retry"),
        occurrence_key=OccurrenceKey(
            schedule_id=ScheduleId("schedule-retry"),
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        ),
        target=TargetRef.python("retry-target"),
        created_at=_instant(),
        retry_policy=retry,
    )
    with factory() as uow:
        uow.requests.add(request)
        uow.commit()

    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(
        request_id=request.id,
        created_at=_instant(),
        policy_snapshot=ExecutionPolicySnapshot(retry=retry),
    )
    return service, execution


def test_t_retry_run_001_failure_parks_execution_until_retry_deadline() -> None:
    factory = InMemoryUnitOfWorkFactory()
    retry = RetryPolicy(
        max_attempts=3,
        backoff=FixedBackoff(Duration.minutes(5)),
    )
    service, execution = _dispatch(factory, retry=retry)
    clock = MutableClock(_instant())
    registry = PythonTargetRegistry()

    def target() -> None:
        raise RuntimeError("temporary")

    registry.register("retry-target", target)
    runner = ExecutionRunner(
        uow_factory=factory,
        execution_service=service,
        executor=LocalExecutor(registry=registry, clock=clock),
        clock=clock,
    )

    result = runner.run(execution_id=execution.id)

    assert result.execution.state is ExecutionState.RETRY_WAIT
    assert result.execution.attempt_count == 1
    assert result.execution.next_attempt_at == _instant().add(Duration.minutes(5))
    assert result.retry_decision is not None
    assert result.retry_decision.reason is RetryDecisionReason.RETRYABLE_FAILURE

    with factory() as uow:
        assert uow.executions.list_runnable(now=_instant(), limit=10) == []
        due = uow.executions.list_runnable(
            now=_instant().add(Duration.minutes(5)),
            limit=10,
        )
        assert [item.id for item in due] == [execution.id]


def test_t_retry_run_002_retry_preserves_execution_and_creates_next_attempt() -> None:
    factory = InMemoryUnitOfWorkFactory()
    retry = RetryPolicy(max_attempts=2)
    service, execution = _dispatch(factory, retry=retry)
    clock = MutableClock(_instant())
    registry = PythonTargetRegistry()
    calls = 0

    def target() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary")

    registry.register("retry-target", target)
    runner = ExecutionRunner(
        uow_factory=factory,
        execution_service=service,
        executor=LocalExecutor(registry=registry, clock=clock),
        clock=clock,
    )

    first = runner.run(execution_id=execution.id)
    second = runner.run(execution_id=execution.id)

    assert first.execution.id == second.execution.id == execution.id
    assert second.execution.state is ExecutionState.SUCCESS
    assert second.execution.attempt_count == 2

    with factory() as uow:
        attempts = uow.attempts.list_for_execution(execution.id)
        assert [attempt.number for attempt in attempts] == [1, 2]
