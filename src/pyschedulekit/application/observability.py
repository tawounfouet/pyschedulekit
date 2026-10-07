"""Best-effort application observability orchestration."""

from __future__ import annotations

from pyschedulekit.domain.time import Instant
from pyschedulekit.ports.observability import (
    Observation,
    ObservationSink,
    ObservationValue,
)


class Observer:
    """Emit structured observations without allowing telemetry failures to break scheduling."""

    def __init__(self, sink: ObservationSink | None = None) -> None:
        self._sink = sink

    @property
    def enabled(self) -> bool:
        return self._sink is not None

    def record(
        self,
        *,
        name: str,
        recorded_at: Instant,
        **attributes: ObservationValue,
    ) -> None:
        """Record one observation on a best-effort basis."""

        if self._sink is None:
            return

        try:
            self._sink.record(
                Observation.from_mapping(
                    name=name,
                    recorded_at=recorded_at,
                    attributes=attributes,
                )
            )
        except Exception:
            # Observability is diagnostic and must never become a scheduler
            # correctness dependency.
            return
