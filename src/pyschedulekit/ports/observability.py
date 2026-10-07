"""Observability ports for structured, dependency-neutral scheduler telemetry."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, TypeAlias

from pyschedulekit.domain.time import Instant

ObservationValue: TypeAlias = str | int | float | bool


@dataclass(frozen=True, slots=True)
class Observation:
    """Immutable structured telemetry record emitted by PyScheduleKit."""

    name: str
    recorded_at: Instant
    attributes: tuple[tuple[str, ObservationValue], ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Observation name must not be empty.")

        keys = tuple(key for key, _ in self.attributes)
        if any(not key.strip() for key in keys):
            raise ValueError("Observation attribute names must not be empty.")
        if len(set(keys)) != len(keys):
            raise ValueError("Observation attribute names must be unique.")

    @classmethod
    def from_mapping(
        cls,
        *,
        name: str,
        recorded_at: Instant,
        attributes: Mapping[str, ObservationValue] | None = None,
    ) -> Observation:
        """Build a deterministic Observation from attribute mappings."""

        normalized = tuple(sorted((attributes or {}).items()))
        return cls(
            name=name,
            recorded_at=recorded_at,
            attributes=normalized,
        )

    def attribute(self, name: str) -> ObservationValue | None:
        """Return one attribute value when present."""

        for key, value in self.attributes:
            if key == name:
                return value
        return None


class ObservationSink(Protocol):
    """Receive structured observations without defining a vendor backend."""

    def record(self, observation: Observation) -> None: ...
