"""Durable schedule-scoped admission lock model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pyschedulekit.domain.claim import WorkerId
from pyschedulekit.domain.schedule import ScheduleId
from pyschedulekit.domain.time import Instant


@dataclass(frozen=True, slots=True)
class AdmissionToken:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("AdmissionToken must not be empty.")


class ScheduleAdmissionLockState(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"


class AdmissionLockOwnershipError(RuntimeError):
    """Raised when a worker tries to release another admission lock."""


class ScheduleAdmissionLock:
    """Short-lived durable lock guarding count-and-admit for one Schedule."""

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
        token: AdmissionToken,
        acquired_at: Instant,
        expires_at: Instant,
        generation: int = 1,
        state: ScheduleAdmissionLockState = ScheduleAdmissionLockState.ACTIVE,
        released_at: Instant | None = None,
        version: int = 0,
    ) -> None:
        if expires_at <= acquired_at:
            raise ValueError("Admission lock expires_at must be after acquired_at.")
        if generation < 1:
            raise ValueError("Admission lock generation must be greater than or equal to 1.")
        if version < 0:
            raise ValueError("Admission lock version must be non-negative.")
        if state is ScheduleAdmissionLockState.ACTIVE and released_at is not None:
            raise ValueError("Active admission lock cannot have released_at.")
        if state is ScheduleAdmissionLockState.RELEASED and released_at is None:
            raise ValueError("Released admission lock requires released_at.")

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
    def token(self) -> AdmissionToken:
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
    def state(self) -> ScheduleAdmissionLockState:
        return self._state

    @property
    def released_at(self) -> Instant | None:
        return self._released_at

    @property
    def version(self) -> int:
        return self._version

    def is_active(self, *, now: Instant) -> bool:
        return self._state is ScheduleAdmissionLockState.ACTIVE and now < self._expires_at

    def reassign(
        self,
        *,
        worker_id: WorkerId,
        token: AdmissionToken,
        acquired_at: Instant,
        expires_at: Instant,
    ) -> None:
        if self.is_active(now=acquired_at):
            raise ValueError("Active admission lock cannot be reassigned before expiry.")
        if expires_at <= acquired_at:
            raise ValueError("Admission lock expires_at must be after acquired_at.")

        self._worker_id = worker_id
        self._token = token
        self._acquired_at = acquired_at
        self._expires_at = expires_at
        self._generation += 1
        self._state = ScheduleAdmissionLockState.ACTIVE
        self._released_at = None
        self._version += 1

    def release(
        self,
        *,
        worker_id: WorkerId,
        token: AdmissionToken,
        generation: int,
        released_at: Instant,
    ) -> bool:
        if (
            self._worker_id != worker_id
            or self._token != token
            or self._generation != generation
        ):
            raise AdmissionLockOwnershipError(
                "Admission lock fencing identity does not match."
            )
        if self._state is ScheduleAdmissionLockState.RELEASED:
            return False
        if not self.is_active(now=released_at):
            raise AdmissionLockOwnershipError(
                "Admission lock is expired or inactive."
            )
        if released_at < self._acquired_at:
            raise ValueError("Admission lock release cannot precede acquisition.")

        self._state = ScheduleAdmissionLockState.RELEASED
        self._released_at = released_at
        self._version += 1
        return True


@dataclass(frozen=True, slots=True)
class ScheduleAdmissionLockHandle:
    schedule_id: ScheduleId
    worker_id: WorkerId
    token: AdmissionToken
    generation: int
    expires_at: Instant
