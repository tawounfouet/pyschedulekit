"""Graceful shutdown coordination for the local scheduler runtime."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from threading import Condition, Event, RLock
from time import monotonic

from pyschedulekit.domain.execution import ExecutionId
from pyschedulekit.domain.time import Duration


class ShutdownMode(StrEnum):
    """Policy applied to work already running when shutdown begins."""

    WAIT = "wait"
    CANCEL = "cancel"


@dataclass(frozen=True, slots=True)
class ShutdownResult:
    """Structured outcome of one graceful shutdown request."""

    mode: ShutdownMode
    completed: bool
    timed_out: bool
    active_execution_ids: tuple[ExecutionId, ...]


class ShutdownGate:
    """Thread-safe barrier preventing new admissions and Attempts during drain."""

    def __init__(self) -> None:
        self._event = Event()

    @property
    def is_requested(self) -> bool:
        return self._event.is_set()

    def request(self) -> None:
        self._event.set()

    def reset(self) -> None:
        self._event.clear()


class ExecutionActivityTracker:
    """Track process-local Executions currently inside executor invocation."""

    def __init__(self) -> None:
        self._active: set[ExecutionId] = set()
        self._condition = Condition(RLock())

    def enter(self, execution_id: ExecutionId) -> None:
        with self._condition:
            self._active.add(execution_id)
            self._condition.notify_all()

    def leave(self, execution_id: ExecutionId) -> None:
        with self._condition:
            self._active.discard(execution_id)
            self._condition.notify_all()

    def snapshot(self) -> tuple[ExecutionId, ...]:
        with self._condition:
            return tuple(sorted(self._active, key=lambda item: item.value))

    def wait_until_empty(self, *, timeout: Duration | None) -> bool:
        deadline = (
            monotonic() + timeout.total_seconds
            if timeout is not None
            else None
        )

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
