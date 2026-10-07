"""Cancellation contracts shared by execution adapters and workloads."""

from __future__ import annotations

from typing import Protocol


class ExecutionCancelledError(RuntimeError):
    """Raised by cooperative workloads after cancellation is requested."""


class CancellationToken(Protocol):
    """Read-only cooperative cancellation signal exposed to workloads."""

    @property
    def is_cancelled(self) -> bool: ...

    def raise_if_cancelled(self) -> None: ...


class CancellationController(Protocol):
    """Control-plane registry for per-Execution cancellation signals."""

    def token_for(self, execution_id: str) -> CancellationToken: ...

    def cancel(self, execution_id: str) -> None: ...

    def release(self, execution_id: str) -> None: ...
