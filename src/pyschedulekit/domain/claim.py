"""Durable distributed execution claim model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pyschedulekit.domain.execution import ExecutionId
from pyschedulekit.domain.time import Instant


@dataclass(frozen=True, slots=True)
class WorkerId:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("WorkerId must not be empty.")


@dataclass(frozen=True, slots=True)
class ClaimToken:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("ClaimToken must not be empty.")


class ExecutionClaimState(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"


class ClaimOwnershipError(RuntimeError):
    """Raised when a worker tries to consume or release another claim."""


class ExecutionClaim:
    """One durable ownership claim for an Execution."""

    __slots__ = (
        "_claimed_at",
        "_execution_id",
        "_expires_at",
        "_released_at",
        "_state",
        "_token",
        "_version",
        "_worker_id",
    )

    def __init__(
        self,
        *,
        execution_id: ExecutionId,
        worker_id: WorkerId,
        token: ClaimToken,
        claimed_at: Instant,
        expires_at: Instant,
        state: ExecutionClaimState = ExecutionClaimState.ACTIVE,
        released_at: Instant | None = None,
        version: int = 0,
    ) -> None:
        if expires_at <= claimed_at:
            raise ValueError("Claim expires_at must be after claimed_at.")
        if version < 0:
            raise ValueError("Claim version must be non-negative.")
        if state is ExecutionClaimState.ACTIVE and released_at is not None:
            raise ValueError("Active claim cannot have released_at.")
        if state is ExecutionClaimState.RELEASED and released_at is None:
            raise ValueError("Released claim requires released_at.")

        self._execution_id = execution_id
        self._worker_id = worker_id
        self._token = token
        self._claimed_at = claimed_at
        self._expires_at = expires_at
        self._state = state
        self._released_at = released_at
        self._version = version

    @property
    def execution_id(self) -> ExecutionId:
        return self._execution_id

    @property
    def worker_id(self) -> WorkerId:
        return self._worker_id

    @property
    def token(self) -> ClaimToken:
        return self._token

    @property
    def claimed_at(self) -> Instant:
        return self._claimed_at

    @property
    def expires_at(self) -> Instant:
        return self._expires_at

    @property
    def state(self) -> ExecutionClaimState:
        return self._state

    @property
    def released_at(self) -> Instant | None:
        return self._released_at

    @property
    def version(self) -> int:
        return self._version

    def is_active(self, *, now: Instant) -> bool:
        return self._state is ExecutionClaimState.ACTIVE and now < self._expires_at

    def reassign(
        self,
        *,
        worker_id: WorkerId,
        token: ClaimToken,
        claimed_at: Instant,
        expires_at: Instant,
    ) -> None:
        if self.is_active(now=claimed_at):
            raise ValueError("Active claim cannot be reassigned before expiry.")
        if expires_at <= claimed_at:
            raise ValueError("Claim expires_at must be after claimed_at.")

        self._worker_id = worker_id
        self._token = token
        self._claimed_at = claimed_at
        self._expires_at = expires_at
        self._state = ExecutionClaimState.ACTIVE
        self._released_at = None
        self._version += 1

    def release(
        self,
        *,
        worker_id: WorkerId,
        token: ClaimToken,
        released_at: Instant,
    ) -> bool:
        if self._worker_id != worker_id or self._token != token:
            raise ClaimOwnershipError("Execution claim ownership token does not match.")
        if self._state is ExecutionClaimState.RELEASED:
            return False
        if released_at < self._claimed_at:
            raise ValueError("Claim release cannot precede acquisition.")

        self._state = ExecutionClaimState.RELEASED
        self._released_at = released_at
        self._version += 1
        return True


@dataclass(frozen=True, slots=True)
class ExecutionClaimHandle:
    execution_id: ExecutionId
    worker_id: WorkerId
    token: ClaimToken
    expires_at: Instant
