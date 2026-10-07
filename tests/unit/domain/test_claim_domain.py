"""LOT-26 unit tests for durable Execution claims."""

from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.claim import (
    ClaimOwnershipError,
    ClaimToken,
    ExecutionClaim,
    ExecutionClaimState,
    WorkerId,
)
from pyschedulekit.domain.execution import ExecutionId
from pyschedulekit.domain.time import Instant


def _instant(second: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, second, tzinfo=UTC))


def _claim() -> ExecutionClaim:
    return ExecutionClaim(
        execution_id=ExecutionId("execution-1"),
        worker_id=WorkerId("worker-a"),
        token=ClaimToken("token-a"),
        claimed_at=_instant(),
        expires_at=_instant(30),
    )


def test_t_claim_unit_001_active_before_expiry() -> None:
    claim = _claim()

    assert claim.state is ExecutionClaimState.ACTIVE
    assert claim.is_active(now=_instant(29))
    assert not claim.is_active(now=_instant(30))


def test_t_claim_unit_002_active_claim_cannot_be_reassigned() -> None:
    claim = _claim()

    with pytest.raises(ValueError, match="Active claim"):
        claim.reassign(
            worker_id=WorkerId("worker-b"),
            token=ClaimToken("token-b"),
            claimed_at=_instant(10),
            expires_at=_instant(40),
        )


def test_t_claim_unit_003_expired_claim_can_be_reassigned() -> None:
    claim = _claim()

    claim.reassign(
        worker_id=WorkerId("worker-b"),
        token=ClaimToken("token-b"),
        claimed_at=_instant(30),
        expires_at=Instant(datetime(2026, 1, 1, 10, 1, 0, tzinfo=UTC)),
    )

    assert claim.worker_id == WorkerId("worker-b")
    assert claim.token == ClaimToken("token-b")
    assert claim.state is ExecutionClaimState.ACTIVE
    assert claim.version == 1


def test_t_claim_unit_004_wrong_owner_cannot_release() -> None:
    claim = _claim()

    with pytest.raises(ClaimOwnershipError):
        claim.release(
            worker_id=WorkerId("worker-b"),
            token=ClaimToken("token-a"),
            released_at=_instant(5),
        )


def test_t_claim_unit_005_release_is_idempotent_for_same_owner() -> None:
    claim = _claim()

    assert claim.release(
        worker_id=WorkerId("worker-a"),
        token=ClaimToken("token-a"),
        released_at=_instant(5),
    )
    assert not claim.release(
        worker_id=WorkerId("worker-a"),
        token=ClaimToken("token-a"),
        released_at=_instant(6),
    )
    assert claim.state is ExecutionClaimState.RELEASED
