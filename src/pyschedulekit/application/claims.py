"""Application coordination for distributed execution claims."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from pyschedulekit.domain.claim import (
    ClaimToken,
    ExecutionClaim,
    ExecutionClaimHandle,
    WorkerId,
)
from pyschedulekit.domain.execution import ExecutionId, ExecutionState
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.ports.persistence import PersistenceConflictError, UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class ClaimAcquisition:
    execution_id: ExecutionId
    acquired: bool
    handle: ExecutionClaimHandle | None = None
    reason: str | None = None


class ExecutionClaimCoordinator:
    """Acquire one-shot durable ownership before an Attempt starts."""

    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        worker_id: WorkerId,
        ttl: Duration,
    ) -> None:
        if ttl.total_seconds <= 0:
            raise ValueError("Claim TTL must be greater than zero.")
        self._uow_factory = uow_factory
        self._worker_id = worker_id
        self._ttl = ttl

    @property
    def worker_id(self) -> WorkerId:
        return self._worker_id

    def acquire(
        self,
        *,
        execution_id: ExecutionId,
        now: Instant,
    ) -> ClaimAcquisition:
        token = ClaimToken(uuid4().hex)
        expires_at = now.add(self._ttl)

        try:
            with self._uow_factory() as uow:
                execution = uow.executions.get(execution_id)
                if execution is None:
                    return ClaimAcquisition(
                        execution_id=execution_id,
                        acquired=False,
                        reason="execution_not_found",
                    )
                if execution.state is ExecutionState.RETRY_WAIT:
                    if execution.next_attempt_at is None or execution.next_attempt_at > now:
                        return ClaimAcquisition(
                            execution_id=execution_id,
                            acquired=False,
                            reason="execution_not_runnable",
                        )
                elif execution.state is not ExecutionState.QUEUED:
                    return ClaimAcquisition(
                        execution_id=execution_id,
                        acquired=False,
                        reason="execution_not_runnable",
                    )

                claim = uow.claims.get(execution_id)
                if claim is None:
                    claim = ExecutionClaim(
                        execution_id=execution_id,
                        worker_id=self._worker_id,
                        token=token,
                        claimed_at=now,
                        expires_at=expires_at,
                    )
                    uow.claims.add(claim)
                else:
                    if claim.is_active(now=now):
                        return ClaimAcquisition(
                            execution_id=execution_id,
                            acquired=False,
                            reason="already_claimed",
                        )
                    claim.reassign(
                        worker_id=self._worker_id,
                        token=token,
                        claimed_at=now,
                        expires_at=expires_at,
                    )
                    uow.claims.save(claim)

                uow.commit()
        except PersistenceConflictError:
            return ClaimAcquisition(
                execution_id=execution_id,
                acquired=False,
                reason="claim_conflict",
            )

        return ClaimAcquisition(
            execution_id=execution_id,
            acquired=True,
            handle=ExecutionClaimHandle(
                execution_id=execution_id,
                worker_id=self._worker_id,
                token=token,
                expires_at=expires_at,
            ),
        )

    def release(
        self,
        *,
        handle: ExecutionClaimHandle,
        released_at: Instant,
    ) -> bool:
        try:
            with self._uow_factory() as uow:
                claim = uow.claims.get(handle.execution_id)
                if claim is None:
                    return False
                changed = claim.release(
                    worker_id=handle.worker_id,
                    token=handle.token,
                    released_at=released_at,
                )
                if not changed:
                    return False
                uow.claims.save(claim)
                uow.commit()
                return True
        except PersistenceConflictError:
            return False
