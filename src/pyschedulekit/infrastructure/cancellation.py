"""Thread-safe in-memory cooperative cancellation primitives."""

from __future__ import annotations

from threading import Event, RLock

from pyschedulekit.ports.cancellation import (
    CancellationToken,
    ExecutionCancelledError,
)


class LocalCancellationToken:
    """Thread-safe cancellation token backed by a threading Event."""

    def __init__(self) -> None:
        self._cancelled = Event()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def cancel(self) -> None:
        self._cancelled.set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise ExecutionCancelledError("Execution cancellation was requested.")


class InMemoryCancellationController:
    """Process-local registry preserving one token per logical Execution."""

    def __init__(self) -> None:
        self._tokens: dict[str, LocalCancellationToken] = {}
        self._lock = RLock()

    def token_for(self, execution_id: str) -> CancellationToken:
        with self._lock:
            token = self._tokens.get(execution_id)
            if token is None:
                token = LocalCancellationToken()
                self._tokens[execution_id] = token
            return token

    def cancel(self, execution_id: str) -> None:
        with self._lock:
            token = self._tokens.get(execution_id)
            if token is None:
                token = LocalCancellationToken()
                self._tokens[execution_id] = token
            token.cancel()

    def release(self, execution_id: str) -> None:
        with self._lock:
            self._tokens.pop(execution_id, None)
