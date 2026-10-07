"""Transactional outbox message model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from pyschedulekit.domain.time import Instant


class OutboxState(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"


@dataclass(frozen=True, slots=True)
class OutboxMessageId:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("OutboxMessageId must not be empty.")

    @classmethod
    def deterministic(
        cls,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
    ) -> OutboxMessageId:
        canonical = f"{event_type}|{aggregate_type}|{aggregate_id}"
        return cls(sha256(canonical.encode("utf-8")).hexdigest())


class OutboxMessage:
    """Durable message persisted atomically with scheduler state."""

    __slots__ = (
        "_aggregate_id",
        "_aggregate_type",
        "_created_at",
        "_event_type",
        "_id",
        "_last_error",
        "_payload",
        "_publish_attempts",
        "_published_at",
        "_sequence",
        "_state",
        "_version",
    )

    def __init__(
        self,
        *,
        message_id: OutboxMessageId,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: tuple[tuple[str, str], ...],
        created_at: Instant,
        sequence: int = 0,
        state: OutboxState = OutboxState.PENDING,
        published_at: Instant | None = None,
        publish_attempts: int = 0,
        last_error: str | None = None,
        version: int = 0,
    ) -> None:
        if not event_type.strip():
            raise ValueError("event_type must not be empty.")
        if not aggregate_type.strip():
            raise ValueError("aggregate_type must not be empty.")
        if not aggregate_id.strip():
            raise ValueError("aggregate_id must not be empty.")
        if sequence < 0:
            raise ValueError("sequence must be non-negative.")
        if publish_attempts < 0:
            raise ValueError("publish_attempts must be non-negative.")
        if version < 0:
            raise ValueError("version must be non-negative.")
        if state is OutboxState.PUBLISHED and published_at is None:
            raise ValueError("Published outbox message requires published_at.")
        if state is OutboxState.PENDING and published_at is not None:
            raise ValueError("Pending outbox message cannot have published_at.")

        self._id = message_id
        self._event_type = event_type
        self._aggregate_type = aggregate_type
        self._aggregate_id = aggregate_id
        self._payload = tuple(sorted(payload))
        self._created_at = created_at
        self._sequence = sequence
        self._state = state
        self._published_at = published_at
        self._publish_attempts = publish_attempts
        self._last_error = last_error
        self._version = version

    @classmethod
    def create(
        cls,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: tuple[tuple[str, str], ...],
        created_at: Instant,
        sequence: int = 0,
    ) -> OutboxMessage:
        return cls(
            message_id=OutboxMessageId.deterministic(
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
            ),
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            created_at=created_at,
            sequence=sequence,
        )

    @property
    def id(self) -> OutboxMessageId:
        return self._id

    @property
    def event_type(self) -> str:
        return self._event_type

    @property
    def aggregate_type(self) -> str:
        return self._aggregate_type

    @property
    def aggregate_id(self) -> str:
        return self._aggregate_id

    @property
    def payload(self) -> tuple[tuple[str, str], ...]:
        return self._payload

    @property
    def created_at(self) -> Instant:
        return self._created_at

    @property
    def sequence(self) -> int:
        return self._sequence

    @property
    def state(self) -> OutboxState:
        return self._state

    @property
    def published_at(self) -> Instant | None:
        return self._published_at

    @property
    def publish_attempts(self) -> int:
        return self._publish_attempts

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def version(self) -> int:
        return self._version

    def mark_published(self, *, published_at: Instant) -> None:
        if self._state is OutboxState.PUBLISHED:
            return
        if published_at < self._created_at:
            raise ValueError("published_at cannot precede created_at.")

        self._state = OutboxState.PUBLISHED
        self._published_at = published_at
        self._publish_attempts += 1
        self._last_error = None
        self._version += 1

    def record_failure(self, *, error: str) -> None:
        if self._state is OutboxState.PUBLISHED:
            raise ValueError("Published outbox message cannot record a publish failure.")
        normalized = error.strip()
        if not normalized:
            raise ValueError("Outbox publish failure must not be empty.")

        self._publish_attempts += 1
        self._last_error = normalized
        self._version += 1
