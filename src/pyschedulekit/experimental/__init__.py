"""Experimental APIs without compatibility guarantees before PyScheduleKit 1.0."""

from pyschedulekit.domain.admission_lock import (
    AdmissionLockOwnershipError,
    AdmissionToken,
    ScheduleAdmissionLock,
    ScheduleAdmissionLockHandle,
    ScheduleAdmissionLockState,
)
from pyschedulekit.domain.claim import (
    ClaimOwnershipError,
    ClaimToken,
    ExecutionClaim,
    ExecutionClaimHandle,
    ExecutionClaimState,
)
from pyschedulekit.domain.misfire import LatenessStatus

__all__ = [
    "AdmissionLockOwnershipError",
    "AdmissionToken",
    "ClaimOwnershipError",
    "ClaimToken",
    "ExecutionClaim",
    "ExecutionClaimHandle",
    "ExecutionClaimState",
    "LatenessStatus",
    "ScheduleAdmissionLock",
    "ScheduleAdmissionLockHandle",
    "ScheduleAdmissionLockState",
]
