"""Application coordination for schedule materialization leases."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from pyschedulekit.domain.claim import WorkerId
from pyschedulekit.domain.materialization_lease import (
    MaterializationLeaseOwnershipError,
    MaterializationToken,
    ScheduleMaterializationLease,
    ScheduleMaterializationLeaseHandle,
)
from pyschedulekit.domain.schedule import ScheduleId
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.ports.persistence import PersistenceConflictError, UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class MaterializationLeaseAcquisition:
    schedule_id: ScheduleId
    acquired: bool
    handle: ScheduleMaterializationLeaseHandle | None = None
    reason: str | None = None


class ScheduleMaterializationCoordinator:
    """Acquire fenced durable ownership for one Schedule materialization."""

    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        worker_id: WorkerId,
        ttl: Duration,
    ) -> None:
        if ttl.total_seconds <= 0:
            raise ValueError("Materialization lease TTL must be greater than zero.")
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
        schedule_id: ScheduleId,
        now: Instant,
    ) -> MaterializationLeaseAcquisition:
        token = MaterializationToken(uuid4().hex)
        expires_at = now.add(self._ttl)

        try:
            with self._uow_factory() as uow:
                schedule = uow.schedules.get(schedule_id)
                if schedule is None:
                    return MaterializationLeaseAcquisition(
                        schedule_id=schedule_id,
                        acquired=False,
                        reason="schedule_not_found",
                    )

                lease = uow.materialization_leases.get(schedule_id)
                if lease is None:
                    lease = ScheduleMaterializationLease(
                        schedule_id=schedule_id,
                        worker_id=self._worker_id,
                        token=token,
                        acquired_at=now,
                        expires_at=expires_at,
                    )
                    uow.materialization_leases.add(lease)
                else:
                    if lease.is_active(now=now):
                        return MaterializationLeaseAcquisition(
                            schedule_id=schedule_id,
                            acquired=False,
                            reason="already_owned",
                        )
                    lease.reassign(
                        worker_id=self._worker_id,
                        token=token,
                        acquired_at=now,
                        expires_at=expires_at,
                    )
                    uow.materialization_leases.save(lease)

                uow.commit()
        except PersistenceConflictError:
            return MaterializationLeaseAcquisition(
                schedule_id=schedule_id,
                acquired=False,
                reason="lease_conflict",
            )

        return MaterializationLeaseAcquisition(
            schedule_id=schedule_id,
            acquired=True,
            handle=ScheduleMaterializationLeaseHandle(
                schedule_id=schedule_id,
                worker_id=self._worker_id,
                token=token,
                generation=lease.generation,
                expires_at=expires_at,
            ),
        )

    def release(
        self,
        *,
        handle: ScheduleMaterializationLeaseHandle,
        released_at: Instant,
    ) -> bool:
        try:
            with self._uow_factory() as uow:
                lease = uow.materialization_leases.get(handle.schedule_id)
                if lease is None:
                    return False
                changed = lease.release(
                    worker_id=handle.worker_id,
                    token=handle.token,
                    generation=handle.generation,
                    released_at=released_at,
                )
                if not changed:
                    return False
                uow.materialization_leases.save(lease)
                uow.commit()
                return True
        except (PersistenceConflictError, MaterializationLeaseOwnershipError):
            return False
