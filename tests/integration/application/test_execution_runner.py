"""LOT-10 integration tests for ExecutionRunner and LocalExecutor."""

from datetime import UTC, datetime

import pytest

from pyschedulekit.application.execution_runner import ExecutionRunner
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.domain.execution import AttemptState, Execution, ExecutionState
from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.schedule import ScheduleId, ScheduleRevision, TargetRef
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.infrastructure.local_executor import LocalExecutor, PythonTargetRegistry
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.ports.executor import TargetResolutionError, UnsupportedTargetError
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0, second: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, second, tzinfo=UTC))


def _persist_request(
    factory: InMemoryUnitOfWorkFactory,
    *,
    target: TargetRef,
    request_id: str = "request-1",
) -> ExecutionRequest:
    request = ExecutionRequest(
        id=RequestId(request_id),
        occurrence_key=OccurrenceKey(
            schedule_id=ScheduleId("schedule-1"),
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        ),
        target=target,
        created_at=_instant(hour=9, minute=59),
    )
    with factory() as uow:
        uow.requests.add(request)
        uow.commit()
    return request


def _dispatch(
    factory: InMemoryUnitOfWorkFactory,
    *,
    target: TargetRef,
) -> tuple[ExecutionService, Execution]:
    request = _persist_request(factory, target=target)
    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(
        request_id=request.id,
        created_at=_instant(),
    )
    return service, execution


def _runner(
    *,
    factory: InMemoryUnitOfWorkFactory,
    service: ExecutionService,
    registry: PythonTargetRegistry,
    clock: MutableClock,
) -> ExecutionRunner:
    return ExecutionRunner(
        uow_factory=factory,
        execution_service=service,
        executor=LocalExecutor(registry=registry, clock=clock),
        clock=clock,
    )


def test_t_run_020_successful_local_callable_completes_execution() -> None:
    factory = InMemoryUnitOfWorkFactory()
    service, execution = _dispatch(
        factory,
        target=TargetRef.python("refresh"),
    )
    clock = MutableClock(_instant())
    registry = PythonTargetRegistry()
    calls: list[str] = []

    def target() -> None:
        calls.append("called")
        clock.advance(Duration.seconds(2))

    registry.register("refresh", target)

    result = _runner(
        factory=factory,
        service=service,
        registry=registry,
        clock=clock,
    ).run(execution_id=execution.id)

    assert calls == ["called"]
    assert result.outcome.succeeded
    assert result.execution.state is ExecutionState.SUCCESS
    assert result.execution.result is not None
    assert result.execution.result.completed_at == _instant(second=2)

    with factory() as uow:
        attempts = uow.attempts.list_for_execution(execution.id)
        assert len(attempts) == 1
        assert attempts[0].state is AttemptState.SUCCESS
        assert attempts[0].started_at == _instant()
        assert attempts[0].result is not None
        assert attempts[0].result.completed_at == _instant(second=2)


def test_t_run_021_callable_exception_becomes_failed_attempt_and_execution() -> None:
    factory = InMemoryUnitOfWorkFactory()
    service, execution = _dispatch(
        factory,
        target=TargetRef.python("failing"),
    )
    clock = MutableClock(_instant())
    registry = PythonTargetRegistry()

    def target() -> None:
        clock.advance(Duration.seconds(3))
        raise ValueError("sensitive customer payload")

    registry.register("failing", target)

    result = _runner(
        factory=factory,
        service=service,
        registry=registry,
        clock=clock,
    ).run(execution_id=execution.id)

    assert not result.outcome.succeeded
    assert result.outcome.failure is not None
    assert result.outcome.failure.code == "python.exception"
    assert result.execution.state is ExecutionState.FAILED
    assert result.execution.result is not None
    assert result.execution.result.failure == result.outcome.failure
    assert result.execution.result.completed_at == _instant(second=3)


def test_t_run_022_target_resolution_error_occurs_before_attempt_creation() -> None:
    factory = InMemoryUnitOfWorkFactory()
    service, execution = _dispatch(
        factory,
        target=TargetRef.python("missing"),
    )
    clock = MutableClock(_instant())
    runner = _runner(
        factory=factory,
        service=service,
        registry=PythonTargetRegistry(),
        clock=clock,
    )

    with pytest.raises(TargetResolutionError):
        runner.run(execution_id=execution.id)

    with factory() as uow:
        persisted = uow.executions.get(execution.id)
        attempts = uow.attempts.list_for_execution(execution.id)
        assert persisted is not None
        assert persisted.state is ExecutionState.QUEUED
        assert persisted.attempt_count == 0
        assert attempts == []


def test_t_run_023_unsupported_target_kind_occurs_before_attempt_creation() -> None:
    factory = InMemoryUnitOfWorkFactory()
    service, execution = _dispatch(
        factory,
        target=TargetRef.workflow("workflow-1"),
    )
    clock = MutableClock(_instant())
    runner = _runner(
        factory=factory,
        service=service,
        registry=PythonTargetRegistry(),
        clock=clock,
    )

    with pytest.raises(UnsupportedTargetError):
        runner.run(execution_id=execution.id)

    with factory() as uow:
        persisted = uow.executions.get(execution.id)
        assert persisted is not None
        assert persisted.state is ExecutionState.QUEUED
        assert uow.attempts.list_for_execution(execution.id) == []


def test_t_run_024_attempt_is_durably_running_before_target_side_effect() -> None:
    factory = InMemoryUnitOfWorkFactory()
    service, execution = _dispatch(
        factory,
        target=TargetRef.python("inspect-state"),
    )
    clock = MutableClock(_instant())
    registry = PythonTargetRegistry()
    observed: list[tuple[ExecutionState, AttemptState]] = []

    def target() -> None:
        with factory() as uow:
            persisted = uow.executions.get(execution.id)
            attempts = uow.attempts.list_for_execution(execution.id)
            assert persisted is not None
            assert len(attempts) == 1
            observed.append((persisted.state, attempts[0].state))

    registry.register("inspect-state", target)

    result = _runner(
        factory=factory,
        service=service,
        registry=registry,
        clock=clock,
    ).run(execution_id=execution.id)

    assert observed == [(ExecutionState.RUNNING, AttemptState.RUNNING)]
    assert result.execution.state is ExecutionState.SUCCESS


def test_t_run_025_base_exception_leaves_running_state_for_recovery() -> None:
    class SimulatedProcessCrash(BaseException):
        pass

    factory = InMemoryUnitOfWorkFactory()
    service, execution = _dispatch(
        factory,
        target=TargetRef.python("crash"),
    )
    clock = MutableClock(_instant())
    registry = PythonTargetRegistry()

    def target() -> None:
        clock.advance(Duration.seconds(1))
        raise SimulatedProcessCrash

    registry.register("crash", target)
    runner = _runner(
        factory=factory,
        service=service,
        registry=registry,
        clock=clock,
    )

    with pytest.raises(SimulatedProcessCrash):
        runner.run(execution_id=execution.id)

    with factory() as uow:
        persisted = uow.executions.get(execution.id)
        attempts = uow.attempts.list_for_execution(execution.id)
        assert persisted is not None
        assert persisted.state is ExecutionState.RUNNING
        assert persisted.active_attempt_number == 1
        assert len(attempts) == 1
        assert attempts[0].state is AttemptState.RUNNING


def test_t_run_026_local_executor_does_not_apply_retry_policy_implicitly() -> None:
    factory = InMemoryUnitOfWorkFactory()
    service, execution = _dispatch(
        factory,
        target=TargetRef.python("fails-once"),
    )
    clock = MutableClock(_instant())
    registry = PythonTargetRegistry()

    def target() -> None:
        raise RuntimeError("temporary")

    registry.register("fails-once", target)

    result = _runner(
        factory=factory,
        service=service,
        registry=registry,
        clock=clock,
    ).run(execution_id=execution.id)

    assert result.execution.state is ExecutionState.FAILED
    assert result.execution.next_attempt_at is None

    with factory() as uow:
        attempts = uow.attempts.list_for_execution(execution.id)
        assert [attempt.number for attempt in attempts] == [1]
