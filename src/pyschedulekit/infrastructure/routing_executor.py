"""Executor routing across declarative target kinds."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from pyschedulekit.domain.schedule import TargetRef
from pyschedulekit.domain.time import Duration
from pyschedulekit.errors import PyScheduleKitConfigurationError
from pyschedulekit.ports.cancellation import CancellationToken
from pyschedulekit.ports.executor import (
    Executor,
    ExecutorOutcome,
    PreparedTarget,
    TargetResolutionError,
    UnsupportedTargetError,
)


@dataclass(frozen=True, slots=True)
class RoutedPreparedTarget:
    """Prepared target bound to the concrete Executor that resolved it."""

    target: TargetRef
    executor: Executor
    prepared: PreparedTarget


class RoutingExecutor:
    """Route each TargetRef kind to one explicitly configured Executor."""

    def __init__(self, executors: Mapping[str, Executor]) -> None:
        normalized: dict[str, Executor] = {}
        for kind, executor in executors.items():
            target_kind = kind.strip()
            if not target_kind:
                raise PyScheduleKitConfigurationError(
                    "Executor target kind must not be empty."
                )
            if target_kind in normalized:
                raise PyScheduleKitConfigurationError(
                    f"Duplicate executor target kind: {target_kind!r}."
                )
            normalized[target_kind] = executor

        if not normalized:
            raise PyScheduleKitConfigurationError(
                "RoutingExecutor requires at least one executor."
            )

        self._executors = normalized

    @property
    def target_kinds(self) -> tuple[str, ...]:
        return tuple(sorted(self._executors))

    def prepare(self, target: TargetRef) -> RoutedPreparedTarget:
        executor = self._executors.get(target.kind)
        if executor is None:
            raise UnsupportedTargetError(
                f"No executor is registered for target kind {target.kind!r}."
            )

        prepared = executor.prepare(target)
        if prepared.target != target:
            raise TargetResolutionError(
                "Executor prepared a target different from the requested TargetRef."
            )
        return RoutedPreparedTarget(
            target=target,
            executor=executor,
            prepared=prepared,
        )

    def execute(
        self,
        prepared: PreparedTarget,
        *,
        timeout: Duration | None = None,
        cancellation_token: CancellationToken | None = None,
        fencing_token: int | None = None,
        idempotency_key: str | None = None,
    ) -> ExecutorOutcome:
        if not isinstance(prepared, RoutedPreparedTarget):
            raise TargetResolutionError(
                "RoutingExecutor can only execute RoutedPreparedTarget values."
            )

        return prepared.executor.execute(
            prepared.prepared,
            timeout=timeout,
            cancellation_token=cancellation_token,
            fencing_token=fencing_token,
            idempotency_key=idempotency_key,
        )
