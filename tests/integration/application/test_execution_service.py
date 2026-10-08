"""LOT-09 integration tests for ExecutionService and persistence."""

from datetime import UTC, datetime

from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.domain.execution import (
    AttemptState,
    ExecutionState,
    Failure,
    FailureCategory,
)
from pyschedulekit.domain.execution_request import (
    ExecutionRequest,
    ExecutionRequestState,
    RequestId,
)
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleRevision,
    ScheduleState,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.testing import add_request_with_parent


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _request(
    *,
    request_id: str = "request-1",
    schedule_id: str = "schedule-1",
    target: str = "app.tasks:refresh",
) -> ExecutionRequest:
    return ExecutionRequest(
        id=RequestId(request_id),
        occurrence_key=OccurrenceKey(
            schedule_id=ScheduleId(schedule_id),
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        ),
        target=TargetRef.python(target),
        created_at=_instant(hour=9, minute=59),
    )


def _persist_request(
    factory: InMemoryUnitOfWorkFactory,
    request: ExecutionRequest,
) -> None:
    with factory() as uow:
        add_request_with_parent(uow=uow, request=request)
        uow.commit()


def _schedule(schedule_id: str = "schedule-1") -> Schedule:
    return Schedule.create(
        schedule_id=ScheduleId(schedule_id),
        definition=ScheduleDefinition(
            target=TargetRef.python("app.tasks:old"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(),
            ),
        ),
        reference=_instant(hour=9),
    )


def test_dispatch_atomically_marks_request_and_creates_queued_execution() -> None:
    factory = InMemoryUnitOfWorkFactory()
    request = _request()
    _persist_request(factory, request)
    service = ExecutionService(uow_factory=factory)

    execution = service.dispatch(
        request_id=request.id,
        created_at=_instant(),
    )

    assert execution.state is ExecutionState.QUEUED
    assert execution.request_id == request.id
    assert execution.target == request.target

    with factory() as uow:
        persisted_request = uow.requests.get(request.id)
        persisted_execution = uow.executions.get_by_request(request.id)

        assert persisted_request is not None
        assert persisted_request.state is ExecutionRequestState.DISPATCHED
        assert persisted_execution is not None
        assert persisted_execution.id == execution.id


def test_dispatch_is_idempotent_after_successful_dispatch() -> None:
    factory = InMemoryUnitOfWorkFactory()
    request = _request()
    _persist_request(factory, request)
    service = ExecutionService(uow_factory=factory)

    first = service.dispatch(request_id=request.id, created_at=_instant())
    second = service.dispatch(
        request_id=request.id,
        created_at=_instant(hour=10, minute=1),
    )

    assert second.id == first.id
    assert second.created_at == first.created_at

    with factory() as uow:
        persisted = uow.executions.get_by_request(request.id)
        assert persisted is not None
        assert persisted.id == first.id


def test_start_attempt_persists_running_execution_and_attempt() -> None:
    factory = InMemoryUnitOfWorkFactory()
    request = _request()
    _persist_request(factory, request)
    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(request_id=request.id, created_at=_instant())

    attempt = service.start_attempt(
        execution_id=execution.id,
        started_at=_instant(hour=10, minute=1),
    )

    assert attempt.state is AttemptState.RUNNING
    assert attempt.number == 1

    with factory() as uow:
        persisted_execution = uow.executions.get(execution.id)
        persisted_attempt = uow.attempts.get(attempt.id)
        assert persisted_execution is not None
        assert persisted_attempt is not None
        assert persisted_execution.state is ExecutionState.RUNNING
        assert persisted_execution.active_attempt_number == 1


def test_successful_attempt_persists_terminal_execution_and_attempt_result() -> None:
    factory = InMemoryUnitOfWorkFactory()
    request = _request()
    _persist_request(factory, request)
    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(request_id=request.id, created_at=_instant())
    attempt = service.start_attempt(
        execution_id=execution.id,
        started_at=_instant(hour=10, minute=1),
    )

    completed = service.succeed_attempt(
        attempt_id=attempt.id,
        completed_at=_instant(hour=10, minute=2),
    )

    assert completed.state is ExecutionState.SUCCESS
    assert completed.result is not None

    with factory() as uow:
        persisted_attempt = uow.attempts.get(attempt.id)
        persisted_execution = uow.executions.get(execution.id)
        assert persisted_attempt is not None
        assert persisted_execution is not None
        assert persisted_attempt.state is AttemptState.SUCCESS
        assert persisted_attempt.result is not None
        assert persisted_execution.state is ExecutionState.SUCCESS


def test_failed_attempt_can_enter_retry_wait_then_start_second_attempt() -> None:
    factory = InMemoryUnitOfWorkFactory()
    request = _request()
    _persist_request(factory, request)
    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(request_id=request.id, created_at=_instant())
    first = service.start_attempt(
        execution_id=execution.id,
        started_at=_instant(hour=10, minute=1),
    )
    failure = Failure(
        category=FailureCategory.TRANSIENT,
        code="target.unavailable",
        message="Temporary failure.",
        occurred_at=_instant(hour=10, minute=2),
        retryable_hint=True,
    )

    waiting = service.fail_attempt(
        attempt_id=first.id,
        failure=failure,
        completed_at=_instant(hour=10, minute=2),
        retry_at=_instant(hour=10, minute=5),
    )

    assert waiting.state is ExecutionState.RETRY_WAIT
    assert waiting.id == execution.id

    second = service.start_attempt(
        execution_id=execution.id,
        started_at=_instant(hour=10, minute=5),
    )

    assert second.number == 2
    assert second.execution_id == execution.id
    assert second.id != first.id

    with factory() as uow:
        attempts = uow.attempts.list_for_execution(execution.id)
        assert [item.number for item in attempts] == [1, 2]


def test_t_sch_012_reschedule_does_not_modify_existing_execution() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _schedule()
    request = _request(target="app.tasks:old")

    with factory() as uow:
        uow.schedules.add(schedule)
        add_request_with_parent(uow=uow, request=request)
        uow.commit()

    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(request_id=request.id, created_at=_instant())

    with factory() as uow:
        persisted_schedule = uow.schedules.get(schedule.id)
        assert persisted_schedule is not None
        persisted_schedule.reschedule(
            definition=ScheduleDefinition(
                target=TargetRef.python("app.tasks:new"),
                trigger=IntervalTrigger(
                    every=Duration.minutes(30),
                    anchor=_instant(),
                ),
            ),
            reference=_instant(),
        )
        uow.schedules.save(persisted_schedule)
        uow.commit()

    with factory() as uow:
        persisted_execution = uow.executions.get(execution.id)
        assert persisted_execution is not None
        assert persisted_execution.target == TargetRef.python("app.tasks:old")
        assert persisted_execution.state is ExecutionState.QUEUED


def test_t_sch_013_pause_schedule_does_not_cancel_existing_execution() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _schedule()
    request = _request()

    with factory() as uow:
        uow.schedules.add(schedule)
        add_request_with_parent(uow=uow, request=request)
        uow.commit()

    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(request_id=request.id, created_at=_instant())

    with factory() as uow:
        persisted_schedule = uow.schedules.get(schedule.id)
        assert persisted_schedule is not None
        persisted_schedule.pause()
        uow.schedules.save(persisted_schedule)
        uow.commit()

    with factory() as uow:
        persisted_schedule = uow.schedules.get(schedule.id)
        persisted_execution = uow.executions.get(execution.id)
        assert persisted_schedule is not None
        assert persisted_execution is not None
        assert persisted_schedule.state is ScheduleState.PAUSED
        assert persisted_execution.state is ExecutionState.QUEUED


def test_t_sch_014_cancel_schedule_does_not_cancel_existing_execution() -> None:
    factory = InMemoryUnitOfWorkFactory()
    schedule = _schedule()
    request = _request()

    with factory() as uow:
        uow.schedules.add(schedule)
        add_request_with_parent(uow=uow, request=request)
        uow.commit()

    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(request_id=request.id, created_at=_instant())

    with factory() as uow:
        persisted_schedule = uow.schedules.get(schedule.id)
        assert persisted_schedule is not None
        persisted_schedule.cancel()
        uow.schedules.save(persisted_schedule)
        uow.commit()

    with factory() as uow:
        persisted_schedule = uow.schedules.get(schedule.id)
        persisted_execution = uow.executions.get(execution.id)
        assert persisted_schedule is not None
        assert persisted_execution is not None
        assert persisted_schedule.state is ScheduleState.CANCELLED
        assert persisted_execution.state is ExecutionState.QUEUED
