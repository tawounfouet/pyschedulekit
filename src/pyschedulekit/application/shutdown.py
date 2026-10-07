"""Graceful shutdown coordination for the local scheduler runtime."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from threading import Condition, RLock
from time import monotonic

from pyschedulekit.domain.execution import ExecutionId
from pyschedulekit.domain.time import Duration


class ShutdownMode(StrEnum):
    """Policy applied to work already running when shutdown begins."""

    WAIT = "wait"
    CANCEL = "cancel"


class ShutdownInProgressError(RuntimeError):
    """Raised when new execution work tries to start during shutdown drain."""


@dataclass(frozen=True, slots=True)
class ShutdownResult:
    """Structured outcome of one graceful shutdown request."""

    mode: ShutdownMode
    completed: bool
    timed_out: bool
    active_execution_ids: tuple[ExecutionId, ...]


class ShutdownCoordinator:
    """Atomically gate new work and track process-local active Executions."""

    def __init__(self) -> None:
        self._condition = Condition(RLock())
        self._requested = False
        self._active: set[ExecutionId] = set()

    @property
    def is_requested(self) -> bool:
        with self._condition:
            return self._requested

    def request(self) -> None:
        with self._condition:
            self._requested = True
            self._condition.notify_all()

    def reset(self) -> None:
        with self._condition:
            if self._active:
                raise RuntimeError(
                    "Cannot reset shutdown coordination while Executions are active."
                )
            self._requested = False
            self._condition.notify_all()

    def try_enter(self, execution_id: ExecutionId) -> bool:
        """Atomically refuse new execution work after shutdown was requested."""

        with self._condition:
            if self._requested:
                return False
            self._active.add(execution_id)
            self._condition.notify_all()
            return True

    def leave(self, execution_id: ExecutionId) -> None:
        with self._condition:
            self._active.discard(execution_id)
            self._condition.notify_all()

    def snapshot(self) -> tuple[ExecutionId, ...]:
        with self._condition:
            return tuple(sorted(self._active, key=lambda item: item.value))

    def wait_until_drained(self, *, timeout: Duration | None) -> bool:
        deadline = monotonic() + timeout.total_seconds if timeout is not None else None

        with self._condition:
            while self._active:
                if deadline is None:
                    self._condition.wait()
                    continue

                remaining = deadline - monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)

            return True
