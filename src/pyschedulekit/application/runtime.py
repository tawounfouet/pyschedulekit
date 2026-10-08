"""Continuous fixed-cadence scheduler runtime."""

from __future__ import annotations

from threading import Event, Lock

from pyschedulekit.application.observability import Observer
from pyschedulekit.application.run_pending import RunPendingResult, RunPendingService
from pyschedulekit.application.wakeup import WakeUpPlanner
from pyschedulekit.domain.time import Duration
from pyschedulekit.errors import PyScheduleKitStateError
from pyschedulekit.ports.runtime import LoopWaiter
from pyschedulekit.ports.time import Clock


class RuntimeAlreadyRunningError(PyScheduleKitStateError):
    """Raised when the same runtime is started more than once concurrently."""


class ContinuousSchedulerLoop:
    """Repeatedly invoke run_pending() at a fixed polling cadence."""

    def __init__(
        self,
        *,
        run_pending_service: RunPendingService,
        waiter: LoopWaiter,
        wakeup_planner: WakeUpPlanner,
        clock: Clock,
        observer: Observer | None = None,
    ) -> None:
        self._run_pending_service = run_pending_service
        self._waiter = waiter
        self._wakeup_planner = wakeup_planner
        self._clock = clock
        self._observer = observer or Observer()
        self._stop_event = Event()
        self._wake_event = Event()
        self._stopped_event = Event()
        self._stopped_event.set()
        self._state_lock = Lock()
        self._running = False
        self._cycles_completed = 0
        self._last_result: RunPendingResult | None = None

    @property
    def is_running(self) -> bool:
        with self._state_lock:
            return self._running

    @property
    def stop_requested(self) -> bool:
        return self._stop_event.is_set()

    @property
    def cycles_completed(self) -> int:
        with self._state_lock:
            return self._cycles_completed

    @property
    def last_result(self) -> RunPendingResult | None:
        with self._state_lock:
            return self._last_result

    def request_stop(self) -> None:
        """Request termination of the loop and interrupt the current wait."""

        self._stop_event.set()
        self._wake_event.set()

    def wait_until_stopped(self, *, timeout: Duration | None) -> bool:
        """Wait until run_forever() has fully returned."""

        if timeout is None:
            self._stopped_event.wait()
            return True
        return self._stopped_event.wait(timeout.total_seconds)

    def wake(self) -> None:
        """Interrupt the current wait so durable state is re-evaluated."""

        self._wake_event.set()

    def run_forever(
        self,
        *,
        max_sleep: Duration,
        limit: int = 100,
    ) -> None:
        """Run adaptive cycles until request_stop() is called."""

        if max_sleep.total_seconds <= 0:
            raise ValueError("max_sleep must be greater than zero.")
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        with self._state_lock:
            if self._running:
                raise RuntimeAlreadyRunningError("Continuous scheduler runtime is already running.")
            self._running = True
            self._stop_event.clear()
            self._wake_event.clear()
            self._stopped_event.clear()

        consecutive_failures = 0
        try:
            while not self._stop_event.is_set():
                try:
                    result = self._run_pending_service.run_pending(limit=limit)
                except Exception as exc:
                    consecutive_failures += 1
                    failed_at = self._clock.now()
                    self._observer.record(
                        name="runtime.cycle.error",
                        recorded_at=failed_at,
                        error_type=type(exc).__name__,
                        consecutive_failures=consecutive_failures,
                        retry_delay_seconds=max_sleep.total_seconds,
                    )

                    if self._stop_event.is_set():
                        break

                    self._wake_event.clear()
                    self._waiter.wait(
                        duration=max_sleep,
                        wake_event=self._wake_event,
                    )
                    if self._stop_event.is_set():
                        break
                    continue

                consecutive_failures = 0
                with self._state_lock:
                    self._cycles_completed += 1
                    cycle_number = self._cycles_completed
                    self._last_result = result

                self._observer.record(
                    name="runtime.cycle.completed",
                    recorded_at=result.evaluation_now,
                    cycle_number=cycle_number,
                )

                if self._stop_event.is_set():
                    break

                self._wake_event.clear()
                delay = self._wakeup_planner.next_delay(max_sleep=max_sleep)
                self._observer.record(
                    name="runtime.wait.planned",
                    recorded_at=result.evaluation_now,
                    delay_seconds=delay.total_seconds,
                )
                if delay.total_seconds <= 0:
                    continue

                self._waiter.wait(
                    duration=delay,
                    wake_event=self._wake_event,
                )
                if self._stop_event.is_set():
                    break
        finally:
            with self._state_lock:
                self._running = False
            self._stopped_event.set()
