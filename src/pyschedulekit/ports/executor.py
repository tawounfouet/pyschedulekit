"""Execution ports separating target resolution from workload invocation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pyschedulekit.domain.execution import Failure
from pyschedulekit.domain.schedule import TargetRef
from pyschedulekit.domain.time import Duration
from pyschedulekit.ports.cancellation import CancellationToken


class ExecutorError(RuntimeError):
    """Base error raised by executor control-plane operations."""


class TargetResolutionError(ExecutorError):
    """Raised when a declarative TargetRef cannot be resolved safely."""


class UnsupportedTargetError(TargetResolutionError):
    """Raised when an executor does not support the TargetRef kind."""


class PreparedTarget(Protocol):
    """Opaque resolved target handle returned by an Executor."""

    @property
    def target(self) -> TargetRef: ...


@dataclass(frozen=True, slots=True)
class ExecutorOutcome:
    """Normalized result of invoking already-prepared workload code."""

    failure: Failure | None = None

    @property
    def succeeded(self) -> bool:
        return self.failure is None


class Executor(Protocol):
    """Port for safe target preparation and workload invocation."""

    def prepare(self, target: TargetRef) -> PreparedTarget:
        """Resolve a TargetRef before an Attempt is started."""
        ...

    def execute(
        self,
        prepared: PreparedTarget,
        *,
        timeout: Duration | None = None,
        cancellation_token: CancellationToken | None = None,
        fencing_token: int | None = None,
    ) -> ExecutorOutcome:
        """Invoke prepared workload code under optional timeout and cancellation."""
        ...
