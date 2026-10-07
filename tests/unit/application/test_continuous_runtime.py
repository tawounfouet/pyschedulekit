"""LOT-18 unit tests for the continuous scheduler loop."""

from datetime import UTC, datetime
from threading import Event, Thread
from time import sleep

import pytest

from pyschedulekit.application.run_pending import RunPendingResult
from pyschedulekit.application.runtime import (
    ContinuousSchedulerLoop,
    RuntimeAlreadyRunningError,
)
from pyschedulekit.domain.time import Duration, Instant


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
        self.entered = Event()
        self.block = Event()

    def run_pending(self, *, limit: int = 100) -> RunPendingResult:
        self.calls.append(limit)
        self.entered.set()
        if not self.block.is_set():
            return _empty_result()
        self.block.wait()
        return _empty_result()


class StopAfterWaits:
    def __init__(self, *, waits: int) -> None:
        self.waits = waits
        self.calls = 0

    def wait(self, *, duration: Duration, stop_event: Event) -> bool:
        assert duration == Duration.seconds(2)
        self.calls += 1
        if self.calls >= self.waits:
            stop_event.set()
            return True
        return False


def test_t_runtime_001_continuous_loop_repeats_run_pending() -> None:
    service = StubRunPendingService()
    waiter = StopAfterWaits(waits=2)
    runtime = ContinuousSchedulerLoop(
        run_pending_service=service,
        waiter=waiter,
    )

    runtime.run_forever(
        poll_interval=Duration.seconds(2),
        limit=7,
    )

    assert service.calls == [7, 7]
    assert runtime.cycles_completed == 2
    assert runtime.last_result is not None
    assert runtime.is_running is False


def test_t_runtime_002_rejects_non_positive_poll_interval() -> None:
    runtime = ContinuousSchedulerLoop(
        run_pending_service=StubRunPendingService(),
        waiter=StopAfterWaits(waits=1),
    )

    with pytest.raises(ValueError, match="poll_interval"):
        runtime.run_forever(poll_interval=Duration.seconds(0))


def test_t_runtime_003_rejects_concurrent_second_start() -> None:
    entered_wait = Event()
    release_wait = Event()

    class BlockingWaiter:
        def wait(self, *, duration: Duration, stop_event: Event) -> bool:
            del duration
            entered_wait.set()
            release_wait.wait(1)
            return stop_event.is_set()

    runtime = ContinuousSchedulerLoop(
        run_pending_service=StubRunPendingService(),
        waiter=BlockingWaiter(),
    )
    worker = Thread(
        target=lambda: runtime.run_forever(
            poll_interval=Duration.seconds(1),
        )
    )
    worker.start()
    assert entered_wait.wait(1)

    with pytest.raises(RuntimeAlreadyRunningError):
        runtime.run_forever(poll_interval=Duration.seconds(1))

    runtime.request_stop()
    release_wait.set()
    worker.join(1)
    assert not worker.is_alive()


def test_t_runtime_004_stop_request_is_idempotent() -> None:
    runtime = ContinuousSchedulerLoop(
        run_pending_service=StubRunPendingService(),
        waiter=StopAfterWaits(waits=1),
    )

    runtime.request_stop()
    runtime.request_stop()

    assert runtime.stop_requested is True
