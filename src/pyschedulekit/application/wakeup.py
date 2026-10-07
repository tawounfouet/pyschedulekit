"""Adaptive wake-up planning for the continuous scheduler runtime."""

from __future__ import annotations

from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.ports.persistence import UnitOfWorkFactory
from pyschedulekit.ports.time import Clock


class WakeUpPlanner:
    """Compute the next useful scheduler delay from durable state."""

    def __init__(
        self,
        *,
        clock: Clock,
        uow_factory: UnitOfWorkFactory,
    ) -> None:
        self._clock = clock
        self._uow_factory = uow_factory

    def next_delay(self, *, max_sleep: Duration) -> Duration:
        if max_sleep.total_seconds <= 0:
            raise ValueError("max_sleep must be greater than zero.")

        now = self._clock.now()
        with self._uow_factory() as uow:
            if uow.requests.has_pending():
                return Duration.seconds(0)

            next_execution = uow.executions.next_runnable_at(now=now)
            next_schedule = uow.schedules.next_run_time()

        next_instant = self._earliest(next_execution, next_schedule)
        if next_instant is None:
            return max_sleep
        if next_instant <= now:
            return Duration.seconds(0)

        until_next = next_instant.elapsed_since(now)
        return min(until_next, max_sleep)

    @staticmethod
    def _earliest(*values: Instant | None) -> Instant | None:
        candidates = [value for value in values if value is not None]
        return min(candidates) if candidates else None
