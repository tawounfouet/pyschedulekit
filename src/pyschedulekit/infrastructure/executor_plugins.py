"""Security-conscious registry for executor adapters and installed plugins."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points
from threading import RLock
from types import MappingProxyType
from typing import cast

from pyschedulekit.errors import PyScheduleKitConfigurationError
from pyschedulekit.ports.executor import Executor

EXECUTOR_ENTRY_POINT_GROUP = "pyschedulekit.executors"


@dataclass(frozen=True, slots=True, order=True)
class ExecutorPluginDescriptor:
    """Metadata for one installed executor entry point.

    Discovery returns descriptors only. It does not import or execute plugin code.
    """

    target_kind: str
    value: str
    distribution: str | None = None


def _installed_executor_entry_points() -> tuple[EntryPoint, ...]:
    """Return installed executor entry points without loading their code."""

    return tuple(entry_points(group=EXECUTOR_ENTRY_POINT_GROUP))


def _validate_target_kind(target_kind: str) -> str:
    normalized = target_kind.strip()
    if not normalized:
        raise PyScheduleKitConfigurationError("Executor target kind must not be empty.")
    return normalized


def _validate_executor(executor: object) -> Executor:
    if not callable(getattr(executor, "prepare", None)):
        raise PyScheduleKitConfigurationError(
            "Executor plugin must expose a callable prepare(target) method."
        )
    if not callable(getattr(executor, "execute", None)):
        raise PyScheduleKitConfigurationError(
            "Executor plugin must expose a callable execute(prepared, ...) method."
        )
    return cast(Executor, executor)


class ExecutorPluginRegistry:
    """Explicit registry and opt-in loader for executor adapters.

    Installed entry points are never loaded merely because they are discoverable. Code is
    imported only when :meth:`activate_entry_point` is called for one exact target kind.
    """

    def __init__(self, executors: Mapping[str, Executor] | None = None) -> None:
        self._executors: dict[str, Executor] = {}
        self._lock = RLock()

        if executors is not None:
            for target_kind, executor in executors.items():
                self.register(target_kind, executor)

    @property
    def target_kinds(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._executors))

    def register(self, target_kind: str, executor: Executor) -> None:
        """Register one explicit executor without silently replacing another."""

        normalized = _validate_target_kind(target_kind)
        validated = _validate_executor(executor)

        with self._lock:
            if normalized in self._executors:
                raise PyScheduleKitConfigurationError(
                    f"Executor target kind {normalized!r} is already registered."
                )
            self._executors[normalized] = validated

    def unregister(self, target_kind: str, executor: Executor) -> bool:
        """Remove one exact executor registration as an explicit compensation."""

        normalized = _validate_target_kind(target_kind)
        with self._lock:
            registered = self._executors.get(normalized)
            if registered is not executor:
                return False
            del self._executors[normalized]
            return True

    def get(self, target_kind: str) -> Executor | None:
        """Return the currently registered executor for one target kind."""

        normalized = _validate_target_kind(target_kind)
        with self._lock:
            return self._executors.get(normalized)

    def discover_entry_points(self) -> tuple[ExecutorPluginDescriptor, ...]:
        """List installed plugin metadata without importing plugin code."""

        descriptors = []
        for entry_point in _installed_executor_entry_points():
            distribution = (
                None
                if entry_point.dist is None
                else entry_point.dist.metadata.get("Name")
            )
            descriptors.append(
                ExecutorPluginDescriptor(
                    target_kind=entry_point.name,
                    value=entry_point.value,
                    distribution=distribution,
                )
            )
        return tuple(sorted(descriptors))

    def activate_entry_point(
        self,
        target_kind: str,
        *,
        config: Mapping[str, object] | None = None,
    ) -> Executor:
        """Explicitly load and register one installed executor plugin.

        The entry-point name is the declarative TargetRef kind. Its loaded object must be a
        factory accepting one read-only configuration mapping and returning an Executor.
        """

        normalized = _validate_target_kind(target_kind)
        matches = [
            entry_point
            for entry_point in _installed_executor_entry_points()
            if entry_point.name == normalized
        ]
        if not matches:
            raise PyScheduleKitConfigurationError(
                f"No installed executor plugin is registered for target kind {normalized!r}."
            )
        if len(matches) > 1:
            raise PyScheduleKitConfigurationError(
                f"Multiple installed executor plugins claim target kind {normalized!r}."
            )

        entry_point = matches[0]
        factory = entry_point.load()
        if not callable(factory):
            raise PyScheduleKitConfigurationError(
                f"Executor plugin {normalized!r} must expose a callable factory."
            )

        readonly_config = MappingProxyType(dict(config or {}))
        executor = _validate_executor(factory(readonly_config))
        self.register(normalized, executor)
        return executor
