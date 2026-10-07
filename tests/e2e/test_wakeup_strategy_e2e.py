"""LOT-19 end-to-end qualification for mutation-driven wake-ups."""

from datetime import UTC, datetime
from threading import Event, Thread
from time import monotonic, sleep

from pyschedulekit import Duration, IntervalTrigger, Scheduler
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0):
    from pyschedulekit import Instant

    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def test_t_wakeup_e2e_001_add_schedule_interrupts_long_runtime_wait() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    called = Event()

    def due_target() -> None:
        called.set()

    scheduler.add_schedule(
        id="existing-future",
        target=due_target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )

    worker = Thread(
        target=lambda: scheduler.run_forever(
            max_sleep=Duration.seconds(30),
        )
    )
    worker.start()

    deadline = monotonic() + 1
    while scheduler.cycles_completed < 1 and monotonic() < deadline:
        sleep(0.001)

    assert scheduler.cycles_completed >= 1

    clock.advance(Duration.minutes(10))

    mutation_started = monotonic()
    scheduler.add_schedule(
        id="wake-mutation",
        target=lambda: None,
        trigger=IntervalTrigger(
            every=Duration.hours(1),
            anchor=_instant(hour=11),
        ),
    )

    assert called.wait(1)
    wake_latency = monotonic() - mutation_started

    scheduler.stop()
    worker.join(1)

    assert not worker.is_alive()
    assert wake_latency < 1
    assert wake_latency < 30
