"""Instance-owned registry for explicit Executor plugins."""

from __future__ import annotations

from collections.abc import Mapping
from threading import RLock

from pyschedulekit.errors import PyScheduleKitConfigurationError
from pyschedulekit.ports.executor import Executor, UnsupportedTargetError


class ExecutorRegistry:
    """Thread-safe mapping from declarative target kinds to Executor instances.

    Registries are deliberately instance-owned. PyScheduleKit never mutates a process-global
    executor registry or imports plugins from persisted target strings.
    """

    def __init__(self, executors: Mapping[str, Executor] | None = None) -> None:
        self._lock = RLock()
        self._executors: dict[str, Executor] = {}

        if executors is not None:
            for kind, executor in executors.items():
                self.register(kind, executor)

    @staticmethod
    def _normalize_kind(kind: str) -> str:
        normalized = kind.strip()
        if not normalized:
            raise PyScheduleKitConfigurationError("Executor target kind must not be empty.")
        return normalized

    def register(
        self,
        kind: str,
        executor: Executor,
        *,
        replace: bool = False,
    ) -> None:
        """Register one explicit Executor for a target kind."""

        normalized = self._normalize_kind(kind)
        with self._lock:
            if normalized in self._executors and not replace:
                raise PyScheduleKitConfigurationError(
                    f"Executor target kind {normalized!r} is already registered."
                )
            self._executors[normalized] = executor

    def unregister(
        self,
        kind: str,
        expected_executor: Executor | None = None,
    ) -> bool:
        """Remove one registration, optionally only when the exact Executor still owns it."""

        normalized = self._normalize_kind(kind)
        with self._lock:
            current = self._executors.get(normalized)
            if current is None:
                return False
            if expected_executor is not None and current is not expected_executor:
                return False
            del self._executors[normalized]
            return True

    def resolve(self, kind: str) -> Executor:
        """Resolve one registered target kind or fail before Attempt execution."""

        normalized = self._normalize_kind(kind)
        with self._lock:
            executor = self._executors.get(normalized)

        if executor is None:
            raise UnsupportedTargetError(
                f"No executor is registered for target kind {normalized!r}."
            )
        return executor

    def contains(self, kind: str) -> bool:
        """Return whether a normalized target kind is explicitly registered."""

        normalized = self._normalize_kind(kind)
        with self._lock:
            return normalized in self._executors

    @property
    def target_kinds(self) -> tuple[str, ...]:
        """Return one deterministic snapshot of registered target kinds."""

        with self._lock:
            return tuple(sorted(self._executors))
