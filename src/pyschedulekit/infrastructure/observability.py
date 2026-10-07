"""Reference observability adapters."""

from __future__ import annotations

from threading import Lock

from pyschedulekit.ports.observability import Observation


class InMemoryObservationSink:
    """Thread-safe observation collector for tests, diagnostics, and embedded use."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._observations: list[Observation] = []

    def record(self, observation: Observation) -> None:
        with self._lock:
            self._observations.append(observation)

    @property
    def observations(self) -> tuple[Observation, ...]:
        with self._lock:
            return tuple(self._observations)

    def by_name(self, name: str) -> tuple[Observation, ...]:
        with self._lock:
            return tuple(
                observation for observation in self._observations if observation.name == name
            )

    def count(self, name: str) -> int:
        return len(self.by_name(name))
