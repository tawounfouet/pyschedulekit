"""Application coordination for schedule-scoped admission locks."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from pyschedulekit.domain.admission_lock import (
    AdmissionToken,
    ScheduleAdmissionLock,
    ScheduleAdmissionLockHandle,
)
from pyschedulekit.domain.claim import WorkerId
from pyschedulekit.domain.schedule import ScheduleId
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.ports.persistence import PersistenceConflictError, UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class AdmissionLockAcquisition:
    schedule_id: ScheduleId
    acquired: bool
    handle: ScheduleAdmissionLockHandle | None = None
    reason: str | None = None


class ScheduleAdmissionLockCoordinator:
    """Acquire short-lived durable ownership around count-and-admit."""

    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        worker_id: WorkerId,
        ttl: Duration,
    ) -> None:
        if ttl.total_seconds <= 0:
            raise ValueError("Admission lock TTL must be greater than zero.")
        self._uow_factory = uow_factory
        self._worker_id = worker_id
        self._ttl = ttl

    def acquire(
        self,
        *,
        schedule_id: ScheduleId,
        now: Instant,
    ) -> AdmissionLockAcquisition:
        token = AdmissionToken(uuid4().hex)
        expires_at = now.add(self._ttl)

        try:
            with self._uow_factory() as uow:
                lock = uow.admission_locks.get(schedule_id)
                if lock is None:
                    lock = ScheduleAdmissionLock(
                        schedule_id=schedule_id,
                        worker_id=self._worker_id,
                        token=token,
                        acquired_at=now,
                        expires_at=expires_at,
                    )
                    uow.admission_locks.add(lock)
                else:
                    if lock.is_active(now=now):
                        return AdmissionLockAcquisition(
                            schedule_id=schedule_id,
                            acquired=False,
                            reason="already_locked",
                        )
                    lock.reassign(
                        worker_id=self._worker_id,
                        token=token,
                        acquired_at=now,
                        expires_at=expires_at,
                    )
                    uow.admission_locks.save(lock)
                uow.commit()
        except PersistenceConflictError:
            return AdmissionLockAcquisition(
                schedule_id=schedule_id,
                acquired=False,
                reason="lock_conflict",
            )

        return AdmissionLockAcquisition(
            schedule_id=schedule_id,
            acquired=True,
            handle=ScheduleAdmissionLockHandle(
                schedule_id=schedule_id,
                worker_id=self._worker_id,
                token=token,
                expires_at=expires_at,
            ),
        )

    def release(
        self,
        *,
        handle: ScheduleAdmissionLockHandle,
        released_at: Instant,
    ) -> bool:
        try:
            with self._uow_factory() as uow:
                lock = uow.admission_locks.get(handle.schedule_id)
                if lock is None:
                    return False
                changed = lock.release(
                    worker_id=handle.worker_id,
                    token=handle.token,
                    released_at=released_at,
                )
                if not changed:
                    return False
                uow.admission_locks.save(lock)
                uow.commit()
                return True
        except PersistenceConflictError:
            return False
