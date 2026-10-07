"""Durable schedule-scoped materialization lease model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pyschedulekit.domain.claim import WorkerId
from pyschedulekit.domain.schedule import ScheduleId
from pyschedulekit.domain.time import Instant


@dataclass(frozen=True, slots=True)
class MaterializationToken:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("MaterializationToken must not be empty.")


class ScheduleMaterializationLeaseState(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"


class MaterializationLeaseOwnershipError(RuntimeError):
    """Raised when a worker uses a stale materialization lease."""


class ScheduleMaterializationLease:
    """Short-lived fenced ownership for materializing one Schedule."""

    __slots__ = (
        "_acquired_at",
        "_expires_at",
        "_generation",
        "_released_at",
        "_schedule_id",
        "_state",
        "_token",
        "_version",
        "_worker_id",
    )

    def __init__(
        self,
        *,
        schedule_id: ScheduleId,
        worker_id: WorkerId,
        token: MaterializationToken,
        acquired_at: Instant,
        expires_at: Instant,
        generation: int = 1,
        state: ScheduleMaterializationLeaseState = ScheduleMaterializationLeaseState.ACTIVE,
        released_at: Instant | None = None,
        version: int = 0,
    ) -> None:
        if expires_at <= acquired_at:
            raise ValueError("Materialization lease expires_at must be after acquired_at.")
        if generation < 1:
            raise ValueError("Materialization lease generation must be greater than or equal to 1.")
        if version < 0:
            raise ValueError("Materialization lease version must be non-negative.")
        if state is ScheduleMaterializationLeaseState.ACTIVE and released_at is not None:
            raise ValueError("Active materialization lease cannot have released_at.")
        if state is ScheduleMaterializationLeaseState.RELEASED and released_at is None:
            raise ValueError("Released materialization lease requires released_at.")

        self._schedule_id = schedule_id
        self._worker_id = worker_id
        self._token = token
        self._acquired_at = acquired_at
        self._expires_at = expires_at
        self._generation = generation
        self._state = state
        self._released_at = released_at
        self._version = version

    @property
    def schedule_id(self) -> ScheduleId:
        return self._schedule_id

    @property
    def worker_id(self) -> WorkerId:
        return self._worker_id

    @property
    def token(self) -> MaterializationToken:
        return self._token

    @property
    def acquired_at(self) -> Instant:
        return self._acquired_at

    @property
    def expires_at(self) -> Instant:
        return self._expires_at

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def state(self) -> ScheduleMaterializationLeaseState:
        return self._state

    @property
    def released_at(self) -> Instant | None:
        return self._released_at

    @property
    def version(self) -> int:
        return self._version

    def is_active(self, *, now: Instant) -> bool:
        return self._state is ScheduleMaterializationLeaseState.ACTIVE and now < self._expires_at

    def reassign(
        self,
        *,
        worker_id: WorkerId,
        token: MaterializationToken,
        acquired_at: Instant,
        expires_at: Instant,
    ) -> None:
        if self.is_active(now=acquired_at):
            raise ValueError("Active materialization lease cannot be reassigned before expiry.")
        if expires_at <= acquired_at:
            raise ValueError("Materialization lease expires_at must be after acquired_at.")

        self._worker_id = worker_id
        self._token = token
        self._acquired_at = acquired_at
        self._expires_at = expires_at
        self._generation += 1
        self._state = ScheduleMaterializationLeaseState.ACTIVE
        self._released_at = None
        self._version += 1

    def release(
        self,
        *,
        worker_id: WorkerId,
        token: MaterializationToken,
        generation: int,
        released_at: Instant,
    ) -> bool:
        if self._worker_id != worker_id or self._token != token or self._generation != generation:
            raise MaterializationLeaseOwnershipError(
                "Materialization lease fencing identity does not match."
            )
        if self._state is ScheduleMaterializationLeaseState.RELEASED:
            return False
        if not self.is_active(now=released_at):
            raise MaterializationLeaseOwnershipError(
                "Materialization lease is expired or inactive."
            )
        if released_at < self._acquired_at:
            raise ValueError("Materialization lease release cannot precede acquisition.")

        self._state = ScheduleMaterializationLeaseState.RELEASED
        self._released_at = released_at
        self._version += 1
        return True


@dataclass(frozen=True, slots=True)
class ScheduleMaterializationLeaseHandle:
    schedule_id: ScheduleId
    worker_id: WorkerId
    token: MaterializationToken
    generation: int
    expires_at: Instant
