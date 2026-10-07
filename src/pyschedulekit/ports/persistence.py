"""Persistence ports for scheduling and execution state."""

from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Protocol

from pyschedulekit.domain.admission_lock import ScheduleAdmissionLock
from pyschedulekit.domain.claim import ExecutionClaim
from pyschedulekit.domain.execution import Attempt, AttemptId, Execution, ExecutionId
from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.materialization_lease import ScheduleMaterializationLease
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.outbox import OutboxMessage, OutboxMessageId
from pyschedulekit.domain.schedule import Schedule, ScheduleId
from pyschedulekit.domain.time import Instant


class PersistenceConflictError(RuntimeError):
    """Base error for optimistic or uniqueness conflicts."""


class OptimisticConcurrencyError(PersistenceConflictError):
    """Raised when committed state changed since an entity was loaded."""


class ReferentialIntegrityError(PersistenceConflictError):
    """Raised when a persistence write violates a relational reference."""


class DatabaseInvariantError(PersistenceConflictError):
    """Raised when a database-level invariant rejects persisted state."""


class DuplicateScheduleError(PersistenceConflictError):
    """Raised when a new Schedule uses an already committed ScheduleId."""


class DuplicateExecutionRequestError(PersistenceConflictError):
    """Raised when a request duplicates an existing ID or OccurrenceKey."""


class DuplicateExecutionError(PersistenceConflictError):
    """Raised when an Execution duplicates an existing ID or RequestId."""


class DuplicateAttemptError(PersistenceConflictError):
    """Raised when an Attempt duplicates an existing ID or attempt number."""


class DuplicateAdmissionLockError(PersistenceConflictError):
    """Raised when a Schedule already owns a persisted admission lock."""


class DuplicateMaterializationLeaseError(PersistenceConflictError):
    """Raised when a Schedule already owns a materialization lease row."""


class DuplicateExecutionClaimError(PersistenceConflictError):
    """Raised when an Execution already owns a persisted claim row."""


class DuplicateOutboxMessageError(PersistenceConflictError):
    """Raised when an outbox message uses an already committed identity."""


class UntrackedEntityError(RuntimeError):
    """Raised when attempting to save an entity not tracked by this UnitOfWork."""


class UntrackedScheduleError(UntrackedEntityError):
    """Backward-compatible Schedule-specific untracked-entity error."""


class ScheduleRepository(Protocol):
    """Transactional repository for Schedule aggregates."""

    def add(self, schedule: Schedule) -> None: ...

    def get(self, schedule_id: ScheduleId) -> Schedule | None: ...

    def save(self, schedule: Schedule) -> None: ...

    def list_due(self, *, now: Instant, limit: int) -> list[Schedule]: ...

    def next_run_time(self) -> Instant | None: ...


class ExecutionRequestRepository(Protocol):
    """Transactional repository for ExecutionRequest entities."""

    def add(self, request: ExecutionRequest) -> None: ...

    def get(self, request_id: RequestId) -> ExecutionRequest | None: ...

    def get_by_occurrence(self, key: OccurrenceKey) -> ExecutionRequest | None: ...

    def save(self, request: ExecutionRequest) -> None: ...

    def list_pending(self, *, limit: int) -> list[ExecutionRequest]: ...

    def list_admission_candidates(self, *, limit: int) -> list[ExecutionRequest]: ...

    def has_pending(self) -> bool: ...

    def list_for_reconciliation(self, *, limit: int) -> list[ExecutionRequest]: ...


class ExecutionRepository(Protocol):
    """Transactional repository for Execution aggregates."""

    def add(self, execution: Execution) -> None: ...

    def get(self, execution_id: ExecutionId) -> Execution | None: ...

    def get_by_request(self, request_id: RequestId) -> Execution | None: ...

    def save(self, execution: Execution) -> None: ...

    def list_queued(self, *, limit: int) -> list[Execution]: ...

    def list_runnable(self, *, now: Instant, limit: int) -> list[Execution]: ...

    def list_running(self, *, limit: int) -> list[Execution]: ...

    def next_runnable_at(self, *, now: Instant) -> Instant | None: ...

    def count_non_terminal_for_schedule(self, schedule_id: ScheduleId) -> int: ...

    def list_for_reconciliation(self, *, limit: int) -> list[Execution]: ...


class AttemptRepository(Protocol):
    """Transactional repository for Attempt entities."""

    def add(self, attempt: Attempt) -> None: ...

    def get(self, attempt_id: AttemptId) -> Attempt | None: ...

    def save(self, attempt: Attempt) -> None: ...

    def list_for_execution(self, execution_id: ExecutionId) -> list[Attempt]: ...


class ScheduleAdmissionLockRepository(Protocol):
    def add(self, lock: ScheduleAdmissionLock) -> None: ...
    def get(self, schedule_id: ScheduleId) -> ScheduleAdmissionLock | None: ...
    def save(self, lock: ScheduleAdmissionLock) -> None: ...


class ScheduleMaterializationLeaseRepository(Protocol):
    """Transactional repository for Schedule materialization ownership."""

    def add(self, lease: ScheduleMaterializationLease) -> None: ...

    def get(self, schedule_id: ScheduleId) -> ScheduleMaterializationLease | None: ...

    def save(self, lease: ScheduleMaterializationLease) -> None: ...


class ExecutionClaimRepository(Protocol):
    """Transactional repository for durable Execution ownership claims."""

    def add(self, claim: ExecutionClaim) -> None: ...

    def get(self, execution_id: ExecutionId) -> ExecutionClaim | None: ...

    def save(self, claim: ExecutionClaim) -> None: ...


class OutboxRepository(Protocol):
    """Transactional repository for durable outbox messages."""

    def add(self, message: OutboxMessage) -> None: ...

    def get(self, message_id: OutboxMessageId) -> OutboxMessage | None: ...

    def save(self, message: OutboxMessage) -> None: ...

    def list_pending(self, *, limit: int) -> list[OutboxMessage]: ...


@dataclass(frozen=True, slots=True)
class RetentionCleanupStats:
    """Actual row/object counts removed by one committed cleanup."""

    execution_graphs: int = 0
    orphan_requests: int = 0
    published_outbox_messages: int = 0

    @property
    def total(self) -> int:
        return self.execution_graphs + self.orphan_requests + self.published_outbox_messages


class RetentionRepository(Protocol):
    """Stage bounded deletion of immutable historical scheduler state."""

    def stage_cleanup(
        self,
        *,
        executions_completed_before: Instant,
        orphan_requests_created_before: Instant,
        outbox_published_before: Instant,
        limit: int,
    ) -> None: ...

    @property
    def result(self) -> RetentionCleanupStats: ...


class UnitOfWork(Protocol):
    """Transactional boundary owning scheduling and execution changes."""

    schedules: ScheduleRepository
    requests: ExecutionRequestRepository
    executions: ExecutionRepository
    attempts: AttemptRepository
    admission_locks: ScheduleAdmissionLockRepository
    materialization_leases: ScheduleMaterializationLeaseRepository
    claims: ExecutionClaimRepository
    outbox: OutboxRepository
    retention: RetentionRepository

    def __enter__(self) -> UnitOfWork: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    """Callable factory producing independent UnitOfWork instances."""

    def __call__(self) -> UnitOfWork: ...
