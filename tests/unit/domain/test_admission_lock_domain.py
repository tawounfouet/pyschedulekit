"""LOT-27 unit tests for schedule admission locks."""

from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.admission_lock import (
    AdmissionLockOwnershipError,
    AdmissionToken,
    ScheduleAdmissionLock,
    ScheduleAdmissionLockState,
)
from pyschedulekit.domain.claim import WorkerId
from pyschedulekit.domain.schedule import ScheduleId
from pyschedulekit.domain.time import Instant


def _instant(second: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, second, tzinfo=UTC))


def _lock() -> ScheduleAdmissionLock:
    return ScheduleAdmissionLock(
        schedule_id=ScheduleId("schedule-1"),
        worker_id=WorkerId("worker-a"),
        token=AdmissionToken("token-a"),
        acquired_at=_instant(),
        expires_at=_instant(5),
    )


def test_t_admission_lock_unit_001_active_until_expiry() -> None:
    lock = _lock()
    assert lock.is_active(now=_instant(4))
    assert not lock.is_active(now=_instant(5))


def test_t_admission_lock_unit_002_active_lock_cannot_be_reassigned() -> None:
    lock = _lock()
    with pytest.raises(ValueError, match="Active admission lock"):
        lock.reassign(
            worker_id=WorkerId("worker-b"),
            token=AdmissionToken("token-b"),
            acquired_at=_instant(2),
            expires_at=_instant(7),
        )


def test_t_admission_lock_unit_003_expired_lock_can_be_reassigned() -> None:
    lock = _lock()
    lock.reassign(
        worker_id=WorkerId("worker-b"),
        token=AdmissionToken("token-b"),
        acquired_at=_instant(5),
        expires_at=_instant(10),
    )
    assert lock.worker_id == WorkerId("worker-b")
    assert lock.state is ScheduleAdmissionLockState.ACTIVE
    assert lock.version == 1


def test_t_admission_lock_unit_004_wrong_owner_cannot_release() -> None:
    lock = _lock()
    with pytest.raises(AdmissionLockOwnershipError):
        lock.release(
            worker_id=WorkerId("worker-b"),
            token=AdmissionToken("token-a"),
            released_at=_instant(1),
        )
