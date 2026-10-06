"""Execution ports separating target resolution from workload invocation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pyschedulekit.domain.execution import Failure
from pyschedulekit.domain.schedule import TargetRef


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

    def execute(self, prepared: PreparedTarget) -> ExecutorOutcome:
        """Invoke prepared workload code and normalize target Exceptions."""
        ...
