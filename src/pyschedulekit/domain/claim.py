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
        "_generation",
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
        generation: int = 1,
        state: ExecutionClaimState = ExecutionClaimState.ACTIVE,
        released_at: Instant | None = None,
        version: int = 0,
    ) -> None:
        if expires_at <= claimed_at:
            raise ValueError("Claim expires_at must be after claimed_at.")
        if generation < 1:
            raise ValueError("Claim generation must be greater than or equal to 1.")
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
        self._generation = generation
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
    def generation(self) -> int:
        return self._generation

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
        self._generation += 1
        self._state = ExecutionClaimState.ACTIVE
        self._released_at = None
        self._version += 1

    def renew(
        self,
        *,
        worker_id: WorkerId,
        token: ClaimToken,
        generation: int,
        renewed_at: Instant,
        expires_at: Instant,
    ) -> None:
        self._assert_owner(
            worker_id=worker_id,
            token=token,
            generation=generation,
        )
        if not self.is_active(now=renewed_at):
            raise ClaimOwnershipError("Execution lease is expired or inactive.")
        if expires_at <= renewed_at:
            raise ValueError("Renewed lease expiry must be after renewed_at.")

        self._expires_at = expires_at
        self._version += 1

    def release(
        self,
        *,
        worker_id: WorkerId,
        token: ClaimToken,
        generation: int,
        released_at: Instant,
    ) -> bool:
        self._assert_owner(
            worker_id=worker_id,
            token=token,
            generation=generation,
        )
        if self._state is ExecutionClaimState.RELEASED:
            return False
        if not self.is_active(now=released_at):
            raise ClaimOwnershipError("Execution lease is expired or inactive.")
        if released_at < self._claimed_at:
            raise ValueError("Claim release cannot precede acquisition.")

        self._state = ExecutionClaimState.RELEASED
        self._released_at = released_at
        self._version += 1
        return True

    def assert_owner(
        self,
        *,
        worker_id: WorkerId,
        token: ClaimToken,
        generation: int,
        now: Instant,
    ) -> None:
        self._assert_owner(
            worker_id=worker_id,
            token=token,
            generation=generation,
        )
        if not self.is_active(now=now):
            raise ClaimOwnershipError("Execution lease is expired or inactive.")

    def _assert_owner(
        self,
        *,
        worker_id: WorkerId,
        token: ClaimToken,
        generation: int,
    ) -> None:
        if self._worker_id != worker_id or self._token != token or self._generation != generation:
            raise ClaimOwnershipError("Execution lease fencing identity does not match.")


@dataclass(frozen=True, slots=True)
class ExecutionClaimHandle:
    execution_id: ExecutionId
    worker_id: WorkerId
    token: ClaimToken
    generation: int
    expires_at: Instant
