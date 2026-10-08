"""POST-00B regression tests for continuous runtime failure supervision."""

from datetime import UTC, datetime
from threading import Event

from pyschedulekit.application.observability import Observer
from pyschedulekit.application.run_pending import RunPendingResult
from pyschedulekit.application.runtime import ContinuousSchedulerLoop
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.infrastructure.observability import InMemoryObservationSink
from pyschedulekit.testing import FixedClock


def _instant() -> Instant:
    return Instant(datetime(2026, 1, 1, tzinfo=UTC))


def _empty_result() -> RunPendingResult:
    return RunPendingResult(
        evaluation_now=_instant(),
        materialized_request_ids=(),
        executions=(),
        schedule_conflicts=(),
        unsupported_policy_schedules=(),
        recovery_limit_schedules=(),
        admissions=(),
        errors=(),
    )


class FailOnceRunPendingService:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def run_pending(self, *, limit: int = 100) -> RunPendingResult:
        self.calls.append(limit)
        if len(self.calls) == 1:
            raise RuntimeError("synthetic cycle failure")
        return _empty_result()


class FixedWakeUpPlanner:
    def next_delay(self, *, max_sleep: Duration) -> Duration:
        return max_sleep


class StopAfterTwoWaits:
    def __init__(self) -> None:
        self.calls = 0
        self.runtime: ContinuousSchedulerLoop | None = None

    def wait(self, *, duration: Duration, wake_event: Event) -> bool:
        assert duration == Duration.seconds(2)
        self.calls += 1
        if self.calls == 2:
            assert self.runtime is not None
            self.runtime.request_stop()
            return True
        return wake_event.is_set()


def test_failed_cycle_is_observed_and_runtime_continues() -> None:
    sink = InMemoryObservationSink()
    service = FailOnceRunPendingService()
    waiter = StopAfterTwoWaits()
    runtime = ContinuousSchedulerLoop(
        run_pending_service=service,
        waiter=waiter,
        wakeup_planner=FixedWakeUpPlanner(),
        clock=FixedClock(_instant()),
        observer=Observer(sink),
    )
    waiter.runtime = runtime

    runtime.run_forever(
        max_sleep=Duration.seconds(2),
        limit=5,
    )

    assert service.calls == [5, 5]
    assert runtime.cycles_completed == 1
    assert runtime.last_result == _empty_result()
    assert runtime.is_running is False

    errors = sink.by_name("runtime.cycle.error")
    assert len(errors) == 1
    assert errors[0].attribute("error_type") == "RuntimeError"
    assert errors[0].attribute("consecutive_failures") == 1
    assert errors[0].attribute("retry_delay_seconds") == 2
