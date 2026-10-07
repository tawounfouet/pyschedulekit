"""LOT-19 unit tests for adaptive wake-up planning."""

from datetime import UTC, datetime

from pyschedulekit import Duration, FixedBackoff, IntervalTrigger, RetryPolicy, Scheduler
from pyschedulekit.application.wakeup import WakeUpPlanner
from pyschedulekit.domain.execution_request import (
    ExecutionRequest,
    ExecutionRequestState,
    RequestId,
)
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.schedule import ScheduleId, ScheduleRevision, TargetRef
from pyschedulekit.domain.time import Instant
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _planner(
    *,
    clock: MutableClock,
    factory: InMemoryUnitOfWorkFactory,
) -> WakeUpPlanner:
    return WakeUpPlanner(clock=clock, uow_factory=factory)


def test_t_wakeup_001_no_known_event_uses_max_sleep() -> None:
    clock = MutableClock(_instant())
    factory = InMemoryUnitOfWorkFactory()

    delay = _planner(clock=clock, factory=factory).next_delay(max_sleep=Duration.seconds(30))

    assert delay == Duration.seconds(30)


def test_t_wakeup_002_next_schedule_shortens_sleep() -> None:
    clock = MutableClock(_instant())
    factory = InMemoryUnitOfWorkFactory()
    scheduler = Scheduler(clock=clock, uow_factory=factory)
    scheduler.add_schedule(
        id="next-schedule",
        target=lambda: None,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )

    delay = _planner(clock=clock, factory=factory).next_delay(max_sleep=Duration.hours(1))

    assert delay == Duration.minutes(10)


def test_t_wakeup_003_due_schedule_returns_zero_delay() -> None:
    clock = MutableClock(_instant())
    factory = InMemoryUnitOfWorkFactory()
    scheduler = Scheduler(clock=clock, uow_factory=factory)
    scheduler.add_schedule(
        id="due-schedule",
        target=lambda: None,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )
    clock.advance(Duration.minutes(10))

    delay = _planner(clock=clock, factory=factory).next_delay(max_sleep=Duration.hours(1))

    assert delay == Duration.seconds(0)


def test_t_wakeup_004_pending_request_returns_zero_delay() -> None:
    clock = MutableClock(_instant())
    factory = InMemoryUnitOfWorkFactory()
    request = ExecutionRequest(
        id=RequestId("pending-request"),
        occurrence_key=OccurrenceKey(
            schedule_id=ScheduleId("pending-schedule"),
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        ),
        target=TargetRef.python("target"),
        created_at=_instant(),
    )
    with factory() as uow:
        uow.requests.add(request)
        uow.commit()

    delay = _planner(clock=clock, factory=factory).next_delay(max_sleep=Duration.seconds(30))

    assert delay == Duration.seconds(0)


def test_t_wakeup_005_waiting_admission_does_not_busy_loop() -> None:
    clock = MutableClock(_instant())
    factory = InMemoryUnitOfWorkFactory()
    request = ExecutionRequest(
        id=RequestId("waiting-request"),
        occurrence_key=OccurrenceKey(
            schedule_id=ScheduleId("waiting-schedule"),
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        ),
        target=TargetRef.python("target"),
        created_at=_instant(),
        state=ExecutionRequestState.WAITING_ADMISSION,
    )
    with factory() as uow:
        uow.requests.add(request)
        uow.commit()

    delay = _planner(clock=clock, factory=factory).next_delay(max_sleep=Duration.seconds(30))

    assert delay == Duration.seconds(30)


def test_t_wakeup_006_retry_deadline_precedes_next_schedule() -> None:
    clock = MutableClock(_instant())
    factory = InMemoryUnitOfWorkFactory()
    scheduler = Scheduler(clock=clock, uow_factory=factory)

    def target() -> None:
        raise RuntimeError("temporary")

    scheduler.add_schedule(
        id="retry-horizon",
        target=target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
        retry=RetryPolicy(
            max_attempts=2,
            backoff=FixedBackoff(Duration.minutes(5)),
        ),
    )

    clock.advance(Duration.minutes(10))
    scheduler.run_pending()

    delay = _planner(clock=clock, factory=factory).next_delay(max_sleep=Duration.hours(1))

    assert delay == Duration.minutes(5)


def test_t_wakeup_007_max_sleep_caps_far_future_event() -> None:
    clock = MutableClock(_instant())
    factory = InMemoryUnitOfWorkFactory()
    scheduler = Scheduler(clock=clock, uow_factory=factory)
    scheduler.add_schedule(
        id="far-future",
        target=lambda: None,
        trigger=IntervalTrigger(
            every=Duration.hours(2),
            anchor=_instant(hour=12),
        ),
    )

    delay = _planner(clock=clock, factory=factory).next_delay(max_sleep=Duration.seconds(20))

    assert delay == Duration.seconds(20)
