"""LOT-16 integration tests for timeout enforcement and retry interaction."""

from datetime import UTC, datetime
from time import monotonic, sleep

from pyschedulekit.application.execution_runner import ExecutionRunner
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.domain.execution import (
    AttemptState,
    ExecutionPolicySnapshot,
    ExecutionState,
    FailureCategory,
)
from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.retry import RetryPolicy
from pyschedulekit.domain.schedule import ScheduleId, ScheduleRevision, TargetRef
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.infrastructure.local_executor import LocalExecutor, PythonTargetRegistry
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.testing import add_request_with_parent
from pyschedulekit.testing import MutableClock


def _instant(second: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, second, tzinfo=UTC))


def _dispatch(
    factory: InMemoryUnitOfWorkFactory,
    *,
    timeout: Duration,
    retry: RetryPolicy | None = None,
):
    request = ExecutionRequest(
        id=RequestId("request-timeout"),
        occurrence_key=OccurrenceKey(
            schedule_id=ScheduleId("schedule-timeout"),
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        ),
        target=TargetRef.python("timeout-target"),
        created_at=_instant(),
        timeout=timeout,
        retry_policy=retry,
    )
    with factory() as uow:
        add_request_with_parent(uow=uow, request=request)
        uow.commit()

    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(
        request_id=request.id,
        created_at=_instant(),
        policy_snapshot=ExecutionPolicySnapshot(
            timeout=timeout,
            retry=retry or RetryPolicy.none(),
        ),
    )
    return service, execution


def test_t_timeout_run_001_elapsed_deadline_marks_attempt_timed_out() -> None:
    factory = InMemoryUnitOfWorkFactory()
    service, execution = _dispatch(
        factory,
        timeout=Duration.seconds(2),
    )
    clock = MutableClock(_instant())
    registry = PythonTargetRegistry()

    def target() -> None:
        clock.advance(Duration.seconds(3))

    registry.register("timeout-target", target)
    runner = ExecutionRunner(
        uow_factory=factory,
        execution_service=service,
        executor=LocalExecutor(registry=registry, clock=clock),
        clock=clock,
    )

    result = runner.run(execution_id=execution.id)

    assert result.outcome.failure is not None
    assert result.outcome.failure.category is FailureCategory.TIMEOUT
    assert result.execution.state is ExecutionState.TIMED_OUT

    with factory() as uow:
        attempts = uow.attempts.list_for_execution(execution.id)
        assert len(attempts) == 1
        assert attempts[0].state is AttemptState.TIMED_OUT


def test_t_timeout_run_002_timeout_can_retry_then_succeed() -> None:
    factory = InMemoryUnitOfWorkFactory()
    retry = RetryPolicy(max_attempts=2)
    service, execution = _dispatch(
        factory,
        timeout=Duration.seconds(2),
        retry=retry,
    )
    clock = MutableClock(_instant())
    registry = PythonTargetRegistry()
    calls = 0

    def target() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            clock.advance(Duration.seconds(3))

    registry.register("timeout-target", target)
    runner = ExecutionRunner(
        uow_factory=factory,
        execution_service=service,
        executor=LocalExecutor(registry=registry, clock=clock),
        clock=clock,
    )

    first = runner.run(execution_id=execution.id)
    second = runner.run(execution_id=execution.id)

    assert first.execution.state is ExecutionState.RETRY_WAIT
    assert second.execution.state is ExecutionState.SUCCESS
    assert second.execution.attempt_count == 2

    with factory() as uow:
        attempts = uow.attempts.list_for_execution(execution.id)
        assert [attempt.state for attempt in attempts] == [
            AttemptState.TIMED_OUT,
            AttemptState.SUCCESS,
        ]


def test_t_timeout_run_003_watchdog_returns_before_blocking_target_finishes() -> None:
    clock = MutableClock(_instant())
    registry = PythonTargetRegistry()

    def target() -> None:
        sleep(0.2)

    registry.register("timeout-target", target)
    executor = LocalExecutor(registry=registry, clock=clock)
    prepared = executor.prepare(TargetRef.python("timeout-target"))

    started = monotonic()
    outcome = executor.execute(
        prepared,
        timeout=Duration.seconds(0.02),
    )
    elapsed = monotonic() - started

    assert elapsed < 0.15
    assert outcome.failure is not None
    assert outcome.failure.category is FailureCategory.TIMEOUT
