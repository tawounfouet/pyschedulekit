"""LOT-18 unit tests for the continuous scheduler loop."""

from datetime import UTC, datetime
from threading import Event, Thread

import pytest

from pyschedulekit.application.observability import Observer
from pyschedulekit.application.run_pending import RunPendingResult
from pyschedulekit.application.runtime import (
    ContinuousSchedulerLoop,
    RuntimeAlreadyRunningError,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.infrastructure.observability import InMemoryObservationSink
from pyschedulekit.testing import FixedClock


def _empty_result() -> RunPendingResult:
    return RunPendingResult(
        evaluation_now=Instant(datetime(2026, 1, 1, tzinfo=UTC)),
        materialized_request_ids=(),
        executions=(),
        schedule_conflicts=(),
        unsupported_policy_schedules=(),
        recovery_limit_schedules=(),
        admissions=(),
        errors=(),
    )


class StubRunPendingService:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def run_pending(self, *, limit: int = 100) -> RunPendingResult:
        self.calls.append(limit)
        return _empty_result()


class StubWakeUpPlanner:
    def next_delay(self, *, max_sleep: Duration) -> Duration:
        return max_sleep


class StopAfterWaits:
    def __init__(self, *, waits: int) -> None:
        self.waits = waits
        self.calls = 0
        self.runtime: ContinuousSchedulerLoop | None = None

    def wait(self, *, duration: Duration, wake_event: Event) -> bool:
        assert duration == Duration.seconds(2)
        self.calls += 1
        if self.calls >= self.waits:
            assert self.runtime is not None
            self.runtime.request_stop()
            return True
        return wake_event.is_set()


def _runtime(
    *,
    service: StubRunPendingService | None = None,
    waiter: StopAfterWaits | None = None,
) -> tuple[ContinuousSchedulerLoop, StubRunPendingService, StopAfterWaits]:
    effective_service = service or StubRunPendingService()
    effective_waiter = waiter or StopAfterWaits(waits=1)
    runtime = ContinuousSchedulerLoop(
        run_pending_service=effective_service,
        waiter=effective_waiter,
        wakeup_planner=StubWakeUpPlanner(),
        clock=FixedClock(_empty_result().evaluation_now),
    )
    effective_waiter.runtime = runtime
    return runtime, effective_service, effective_waiter


def test_t_runtime_001_continuous_loop_repeats_run_pending() -> None:
    runtime, service, _ = _runtime(waiter=StopAfterWaits(waits=2))

    runtime.run_forever(
        max_sleep=Duration.seconds(2),
        limit=7,
    )

    assert service.calls == [7, 7]
    assert runtime.cycles_completed == 2
    assert runtime.last_result is not None
    assert runtime.is_running is False


def test_t_runtime_002_rejects_non_positive_max_sleep() -> None:
    runtime, _, _ = _runtime()

    with pytest.raises(ValueError, match="max_sleep"):
        runtime.run_forever(max_sleep=Duration.seconds(0))


def test_t_runtime_003_rejects_concurrent_second_start() -> None:
    entered_wait = Event()
    release_wait = Event()

    class BlockingWaiter:
        def wait(self, *, duration: Duration, wake_event: Event) -> bool:
            del duration, wake_event
            entered_wait.set()
            release_wait.wait(1)
            return False

    runtime = ContinuousSchedulerLoop(
        run_pending_service=StubRunPendingService(),
        waiter=BlockingWaiter(),
        wakeup_planner=StubWakeUpPlanner(),
        clock=FixedClock(_empty_result().evaluation_now),
    )
    worker = Thread(
        target=lambda: runtime.run_forever(
            max_sleep=Duration.seconds(1),
        )
    )
    worker.start()
    assert entered_wait.wait(1)

    with pytest.raises(RuntimeAlreadyRunningError):
        runtime.run_forever(max_sleep=Duration.seconds(1))

    runtime.request_stop()
    release_wait.set()
    worker.join(1)
    assert not worker.is_alive()


def test_t_runtime_004_stop_request_is_idempotent() -> None:
    runtime, _, _ = _runtime()

    runtime.request_stop()
    runtime.request_stop()

    assert runtime.stop_requested is True


def test_t_runtime_005_emits_cycle_and_wait_observations() -> None:
    sink = InMemoryObservationSink()
    service = StubRunPendingService()
    waiter = StopAfterWaits(waits=1)
    runtime = ContinuousSchedulerLoop(
        run_pending_service=service,
        waiter=waiter,
        wakeup_planner=StubWakeUpPlanner(),
        clock=FixedClock(_empty_result().evaluation_now),
        observer=Observer(sink),
    )
    waiter.runtime = runtime

    runtime.run_forever(
        max_sleep=Duration.seconds(2),
        limit=3,
    )

    cycles = sink.by_name("runtime.cycle.completed")
    waits = sink.by_name("runtime.wait.planned")
    assert len(cycles) == 1
    assert cycles[0].attribute("cycle_number") == 1
    assert len(waits) == 1
    assert waits[0].attribute("delay_seconds") == 2
