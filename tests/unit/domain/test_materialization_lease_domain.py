"""LOT-29 unit tests for Schedule materialization leases."""

from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.claim import WorkerId
from pyschedulekit.domain.materialization_lease import (
    MaterializationLeaseOwnershipError,
    MaterializationToken,
    ScheduleMaterializationLease,
    ScheduleMaterializationLeaseState,
)
from pyschedulekit.domain.schedule import ScheduleId
from pyschedulekit.domain.time import Instant


def _instant(second: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, second, tzinfo=UTC))


def _lease() -> ScheduleMaterializationLease:
    return ScheduleMaterializationLease(
        schedule_id=ScheduleId("schedule-1"),
        worker_id=WorkerId("worker-a"),
        token=MaterializationToken("token-a"),
        acquired_at=_instant(),
        expires_at=_instant(5),
    )


def test_t_materialization_unit_001_active_until_expiry() -> None:
    lease = _lease()

    assert lease.state is ScheduleMaterializationLeaseState.ACTIVE
    assert lease.is_active(now=_instant(4))
    assert not lease.is_active(now=_instant(5))
    assert lease.generation == 1


def test_t_materialization_unit_002_active_lease_cannot_be_reassigned() -> None:
    lease = _lease()

    with pytest.raises(ValueError, match="Active materialization lease"):
        lease.reassign(
            worker_id=WorkerId("worker-b"),
            token=MaterializationToken("token-b"),
            acquired_at=_instant(2),
            expires_at=_instant(7),
        )


def test_t_materialization_unit_003_takeover_increments_generation() -> None:
    lease = _lease()

    lease.reassign(
        worker_id=WorkerId("worker-b"),
        token=MaterializationToken("token-b"),
        acquired_at=_instant(5),
        expires_at=_instant(10),
    )

    assert lease.worker_id == WorkerId("worker-b")
    assert lease.generation == 2
    assert lease.version == 1
    assert lease.state is ScheduleMaterializationLeaseState.ACTIVE


def test_t_materialization_unit_004_stale_owner_cannot_release() -> None:
    lease = _lease()
    lease.reassign(
        worker_id=WorkerId("worker-b"),
        token=MaterializationToken("token-b"),
        acquired_at=_instant(5),
        expires_at=_instant(10),
    )

    with pytest.raises(MaterializationLeaseOwnershipError, match="fencing"):
        lease.release(
            worker_id=WorkerId("worker-a"),
            token=MaterializationToken("token-a"),
            generation=1,
            released_at=_instant(6),
        )


def test_t_materialization_unit_005_owner_release_is_idempotent() -> None:
    lease = _lease()

    assert lease.release(
        worker_id=WorkerId("worker-a"),
        token=MaterializationToken("token-a"),
        generation=1,
        released_at=_instant(1),
    )
    assert not lease.release(
        worker_id=WorkerId("worker-a"),
        token=MaterializationToken("token-a"),
        generation=1,
        released_at=_instant(2),
    )
    assert lease.state is ScheduleMaterializationLeaseState.RELEASED
