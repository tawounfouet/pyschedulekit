"""LOT-18 end-to-end qualification for Scheduler.run_forever()."""

from datetime import UTC, datetime
from threading import Event, Thread
from time import monotonic, sleep

from pyschedulekit import Duration, IntervalTrigger, Scheduler
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0):
    from pyschedulekit import Instant

    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def test_t_runtime_e2e_001_continuous_loop_executes_work_after_time_advances() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    called = Event()

    def target() -> None:
        called.set()

    scheduler.add_schedule(
        id="continuous-runtime",
        target=target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )

    worker = Thread(
        target=lambda: scheduler.run_forever(
            poll_interval=Duration.seconds(0.01),
        )
    )
    worker.start()

    deadline = monotonic() + 1
    while scheduler.cycles_completed < 1 and monotonic() < deadline:
        sleep(0.001)

    clock.advance(Duration.minutes(10))
    assert called.wait(1)

    scheduler.stop()
    worker.join(1)

    assert not worker.is_alive()
    assert scheduler.is_running is False
    assert scheduler.cycles_completed >= 2
    assert scheduler.last_result is not None


def test_t_runtime_e2e_002_stop_interrupts_long_poll_wait() -> None:
    scheduler = Scheduler(clock=MutableClock(_instant()))

    worker = Thread(
        target=lambda: scheduler.run_forever(
            poll_interval=Duration.seconds(30),
        )
    )
    worker.start()

    deadline = monotonic() + 1
    while scheduler.cycles_completed < 1 and monotonic() < deadline:
        sleep(0.001)

    started = monotonic()
    scheduler.stop()
    worker.join(1)
    elapsed = monotonic() - started

    assert not worker.is_alive()
    assert elapsed < 0.5
