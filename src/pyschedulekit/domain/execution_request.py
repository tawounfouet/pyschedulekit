"""Durable scheduling intent created from one logical Occurrence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from pyschedulekit.domain.occurrence import Occurrence, OccurrenceKey
from pyschedulekit.domain.schedule import TargetRef
from pyschedulekit.domain.time import Instant


@dataclass(frozen=True, slots=True)
class RequestId:
    """Stable identity for a scheduler-created ExecutionRequest."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("RequestId must not be empty.")

    @classmethod
    def for_occurrence(cls, key: OccurrenceKey) -> RequestId:
        canonical = "|".join(
            (
                key.schedule_id.value,
                str(key.schedule_revision.value),
                key.scheduled_at.value.isoformat(),
            )
        )
        return cls(sha256(canonical.encode("utf-8")).hexdigest())


class ExecutionRequestState(StrEnum):
    """Minimal LOT-08 request lifecycle; expanded in LOT-09."""

    PENDING = "pending"


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """Immutable durable intent to execute one scheduled Occurrence."""

    id: RequestId
    occurrence_key: OccurrenceKey
    target: TargetRef
    created_at: Instant
    state: ExecutionRequestState = ExecutionRequestState.PENDING

    @classmethod
    def from_occurrence(
        cls,
        *,
        occurrence: Occurrence,
        target: TargetRef,
        created_at: Instant,
    ) -> ExecutionRequest:
        return cls(
            id=RequestId.for_occurrence(occurrence.key),
            occurrence_key=occurrence.key,
            target=target,
            created_at=created_at,
        )
