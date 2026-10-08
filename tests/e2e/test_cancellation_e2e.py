"""LOT-17 end-to-end cancellation qualification through Scheduler."""

from datetime import UTC, datetime
from threading import Event, Thread
from time import sleep

from pyschedulekit import (
    CancellationToken,
    Duration,
    ExecutionId,
    IntervalTrigger,
    RetryPolicy,
    Scheduler,
)
from pyschedulekit import RunPendingResult
from pyschedulekit.domain.execution import ExecutionState
from pyschedulekit.domain.execution_request import RequestId
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.schedule import ScheduleRevision
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0):
    from pyschedulekit import Instant

    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def test_t_cancel_e2e_001_public_scheduler_cancels_running_execution() -> None:
    clock = MutableClock(_instant())
    factory = InMemoryUnitOfWorkFactory()
    scheduler = Scheduler(clock=clock, uow_factory=factory)
    started = Event()
    cycle_box: list[RunPendingResult] = []

    def target(cancellation_token: CancellationToken) -> None:
        started.set()
        while not cancellation_token.is_cancelled:
            sleep(0.001)
        cancellation_token.raise_if_cancelled()

    schedule_id = scheduler.add_schedule(
        id="cancel-public",
        target=target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
        retry=RetryPolicy(max_attempts=3),
    )

    scheduled_at = _instant(hour=10, minute=10)
    request_id = RequestId.for_occurrence(
        OccurrenceKey(
            schedule_id=schedule_id,
            schedule_revision=ScheduleRevision(1),
            scheduled_at=scheduled_at,
        )
    )
    execution_id = ExecutionId.for_request(request_id)

    clock.advance(Duration.minutes(10))
    worker = Thread(target=lambda: cycle_box.append(scheduler.run_pending()))
    worker.start()
    assert started.wait(1)

    cancellation = scheduler.cancel_execution(execution_id)
    worker.join(1)

    assert not worker.is_alive()
    assert cancellation.cancellation_requested
    assert len(cycle_box) == 1
    run_result = cycle_box[0]
    assert len(run_result.executions) == 1
    assert run_result.executions[0].execution.state is ExecutionState.CANCELLED
    assert run_result.executions[0].retry_decision is None
    assert run_result.failed == 1
    assert run_result.retry_scheduled == 0
