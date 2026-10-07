"""Continuous fixed-cadence scheduler runtime."""

from __future__ import annotations

from threading import Event, Lock

from pyschedulekit.application.run_pending import RunPendingResult, RunPendingService
from pyschedulekit.domain.time import Duration
from pyschedulekit.ports.runtime import LoopWaiter


class RuntimeAlreadyRunningError(RuntimeError):
    """Raised when the same runtime is started more than once concurrently."""


class ContinuousSchedulerLoop:
    """Repeatedly invoke run_pending() at a fixed polling cadence."""

    def __init__(
        self,
        *,
        run_pending_service: RunPendingService,
        waiter: LoopWaiter,
    ) -> None:
        self._run_pending_service = run_pending_service
        self._waiter = waiter
        self._stop_event = Event()
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

    def run_forever(
        self,
        *,
        poll_interval: Duration,
        limit: int = 100,
    ) -> None:
        """Run fixed-cadence cycles until request_stop() is called."""

        if poll_interval.total_seconds <= 0:
            raise ValueError("poll_interval must be greater than zero.")
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        with self._state_lock:
            if self._running:
                raise RuntimeAlreadyRunningError(
                    "Continuous scheduler runtime is already running."
                )
            self._running = True
            self._stop_event.clear()

        try:
            while not self._stop_event.is_set():
                result = self._run_pending_service.run_pending(limit=limit)
                with self._state_lock:
                    self._cycles_completed += 1
                    self._last_result = result

                if self._stop_event.is_set():
                    break

                interrupted = self._waiter.wait(
                    duration=poll_interval,
                    stop_event=self._stop_event,
                )
                if interrupted:
                    break
        finally:
            with self._state_lock:
                self._running = False

