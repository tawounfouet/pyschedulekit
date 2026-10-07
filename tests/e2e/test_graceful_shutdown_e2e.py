"""LOT-20 end-to-end graceful shutdown qualification."""

from datetime import UTC, datetime
from threading import Event, Lock, Thread
from time import sleep

from pyschedulekit import (
    CancellationToken,
    Duration,
    ExecutionState,
    IntervalTrigger,
    Scheduler,
    ShutdownMode,
)
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0):
    from pyschedulekit import Instant

    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _due_scheduler() -> tuple[Scheduler, MutableClock]:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    return scheduler, clock


def test_t_shutdown_e2e_001_wait_finishes_current_attempt_without_starting_next() -> None:
    scheduler, clock = _due_scheduler()
    started = Event()
    release = Event()
    calls = 0
    calls_lock = Lock()

    def target() -> None:
        nonlocal calls
        with calls_lock:
            calls += 1
        started.set()
        release.wait(1)

    for schedule_id in ("shutdown-a", "shutdown-b"):
        scheduler.add_schedule(
            id=schedule_id,
            target=target,
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(hour=10, minute=10),
            ),
        )

    clock.advance(Duration.minutes(10))
    runtime_thread = Thread(
        target=lambda: scheduler.run_forever(max_sleep=Duration.seconds(30))
    )
    runtime_thread.start()
    assert started.wait(1)

    result_box = []
    shutdown_thread = Thread(
        target=lambda: result_box.append(
            scheduler.shutdown(
                mode=ShutdownMode.WAIT,
                timeout=Duration.seconds(1),
            )
        )
    )
    shutdown_thread.start()
    sleep(0.02)
    assert shutdown_thread.is_alive()

    release.set()
    shutdown_thread.join(1)
    runtime_thread.join(1)

    assert not shutdown_thread.is_alive()
    assert not runtime_thread.is_alive()
    assert len(result_box) == 1
    assert result_box[0].completed is True
    assert result_box[0].timed_out is False
    assert calls == 1


def test_t_shutdown_e2e_002_cancel_cooperative_attempt_and_wait_for_runtime() -> None:
    scheduler, clock = _due_scheduler()
    started = Event()

    def target(cancellation_token: CancellationToken) -> None:
        started.set()
        while not cancellation_token.is_cancelled:
            sleep(0.001)
        cancellation_token.raise_if_cancelled()

    scheduler.add_schedule(
        id="shutdown-cancel",
        target=target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )

    clock.advance(Duration.minutes(10))
    runtime_thread = Thread(
        target=lambda: scheduler.run_forever(max_sleep=Duration.seconds(30))
    )
    runtime_thread.start()
    assert started.wait(1)

    result = scheduler.shutdown(
        mode=ShutdownMode.CANCEL,
        timeout=Duration.seconds(1),
    )
    runtime_thread.join(1)

    assert result.completed is True
    assert result.timed_out is False
    assert result.active_execution_ids == ()
    assert not runtime_thread.is_alive()
    assert scheduler.last_result is not None
    assert len(scheduler.last_result.executions) == 1
    assert scheduler.last_result.executions[0].execution.state is ExecutionState.CANCELLED


def test_t_shutdown_e2e_003_timeout_reports_still_active_execution() -> None:
    scheduler, clock = _due_scheduler()
    started = Event()
    release = Event()

    def target() -> None:
        started.set()
        release.wait(1)

    scheduler.add_schedule(
        id="shutdown-timeout",
        target=target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )

    clock.advance(Duration.minutes(10))
    runtime_thread = Thread(
        target=lambda: scheduler.run_forever(max_sleep=Duration.seconds(30))
    )
    runtime_thread.start()
    assert started.wait(1)

    result = scheduler.shutdown(
        mode=ShutdownMode.WAIT,
        timeout=Duration.seconds(0.02),
    )

    assert result.completed is False
    assert result.timed_out is True
    assert len(result.active_execution_ids) == 1

    release.set()
    runtime_thread.join(1)
    assert not runtime_thread.is_alive()
