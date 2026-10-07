"""Application coordination for distributed execution claims."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock, Thread
from uuid import uuid4

from pyschedulekit.domain.claim import (
    ClaimOwnershipError,
    ClaimToken,
    ExecutionClaim,
    ExecutionClaimHandle,
    WorkerId,
)
from pyschedulekit.domain.execution import ExecutionId, ExecutionState
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.ports.persistence import PersistenceConflictError, UnitOfWorkFactory
from pyschedulekit.ports.time import Clock


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

    @property
    def ttl(self) -> Duration:
        return self._ttl

    def acquire(
        self,
        *,
        execution_id: ExecutionId,
        now: Instant,
    ) -> ClaimAcquisition:
        return self._acquire(
            execution_id=execution_id,
            now=now,
            allow_running=False,
        )

    def acquire_for_recovery(
        self,
        *,
        execution_id: ExecutionId,
        now: Instant,
    ) -> ClaimAcquisition:
        return self._acquire(
            execution_id=execution_id,
            now=now,
            allow_running=True,
        )

    def _acquire(
        self,
        *,
        execution_id: ExecutionId,
        now: Instant,
        allow_running: bool,
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
                elif execution.state is ExecutionState.RUNNING and allow_running:
                    pass
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
                generation=claim.generation,
                expires_at=expires_at,
            ),
        )

    def renew(
        self,
        *,
        handle: ExecutionClaimHandle,
        renewed_at: Instant,
    ) -> ExecutionClaimHandle | None:
        try:
            with self._uow_factory() as uow:
                claim = uow.claims.get(handle.execution_id)
                if claim is None:
                    return None
                claim.renew(
                    worker_id=handle.worker_id,
                    token=handle.token,
                    generation=handle.generation,
                    renewed_at=renewed_at,
                    expires_at=renewed_at.add(self._ttl),
                )
                uow.claims.save(claim)
                uow.commit()
                return ExecutionClaimHandle(
                    execution_id=claim.execution_id,
                    worker_id=claim.worker_id,
                    token=claim.token,
                    generation=claim.generation,
                    expires_at=claim.expires_at,
                )
        except (PersistenceConflictError, ClaimOwnershipError):
            return None

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
                    generation=handle.generation,
                    released_at=released_at,
                )
                if not changed:
                    return False
                uow.claims.save(claim)
                uow.commit()
                return True
        except (PersistenceConflictError, ClaimOwnershipError):
            return False



class ExecutionLeaseHeartbeat:
    """Renew one Execution lease periodically while workload code is running."""

    def __init__(
        self,
        *,
        coordinator: ExecutionClaimCoordinator,
        clock: Clock,
        handle: ExecutionClaimHandle,
        interval: Duration,
    ) -> None:
        if interval.total_seconds <= 0:
            raise ValueError("Lease heartbeat interval must be greater than zero.")
        if interval >= coordinator.ttl:
            raise ValueError("Lease heartbeat interval must be shorter than the lease TTL.")

        self._coordinator = coordinator
        self._clock = clock
        self._interval = interval
        self._handle = handle
        self._handle_lock = Lock()
        self._stop = Event()
        self._lost = Event()
        self._thread: Thread | None = None

    @property
    def lost(self) -> bool:
        return self._lost.is_set()

    @property
    def current_handle(self) -> ExecutionClaimHandle:
        with self._handle_lock:
            return self._handle

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("Execution lease heartbeat is already started.")

        self._thread = Thread(
            target=self._run,
            name=f"pyschedulekit-lease:{self._handle.execution_id.value}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> ExecutionClaimHandle:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        return self.current_handle

    def _run(self) -> None:
        while not self._stop.wait(self._interval.total_seconds):
            handle = self.current_handle
            renewed = self._coordinator.renew(
                handle=handle,
                renewed_at=self._clock.now(),
            )
            if renewed is None:
                self._lost.set()
                return
            with self._handle_lock:
                self._handle = renewed
