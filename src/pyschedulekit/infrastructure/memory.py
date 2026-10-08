"""Transactional in-memory persistence adapters."""

from __future__ import annotations

from threading import RLock
from types import TracebackType

from pyschedulekit.domain.admission_lock import ScheduleAdmissionLock
from pyschedulekit.domain.claim import ExecutionClaim
from pyschedulekit.domain.execution import (
    Attempt,
    AttemptId,
    Execution,
    ExecutionId,
    ExecutionState,
)
from pyschedulekit.domain.execution_request import (
    ExecutionRequest,
    ExecutionRequestState,
    RequestId,
)
from pyschedulekit.domain.materialization_lease import ScheduleMaterializationLease
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.outbox import OutboxMessage, OutboxMessageId, OutboxState
from pyschedulekit.domain.schedule import (
    PersistenceVersion,
    Schedule,
    ScheduleId,
    ScheduleState,
)
from pyschedulekit.domain.time import Instant
from pyschedulekit.ports.persistence import (
    AttemptRepository,
    DuplicateAdmissionLockError,
    DuplicateAttemptError,
    DuplicateExecutionClaimError,
    DuplicateExecutionError,
    DuplicateExecutionRequestError,
    DuplicateMaterializationLeaseError,
    DuplicateOutboxMessageError,
    DuplicateScheduleError,
    ExecutionClaimRepository,
    ExecutionRepository,
    ExecutionRequestRepository,
    OptimisticConcurrencyError,
    OutboxRepository,
    ReferentialIntegrityError,
    RetentionCleanupStats,
    RetentionRepository,
    ScheduleAdmissionLockRepository,
    ScheduleMaterializationLeaseRepository,
    ScheduleRepository,
    UnitOfWork,
    UntrackedEntityError,
    UntrackedScheduleError,
)


def _clone_schedule(schedule: Schedule) -> Schedule:
    return Schedule(
        schedule_id=schedule.id,
        definition=schedule.definition,
        state=schedule.state,
        revision=schedule.revision,
        persistence_version=schedule.persistence_version,
        next_run_time=schedule.next_run_time,
    )


def _clone_request(request: ExecutionRequest) -> ExecutionRequest:
    return ExecutionRequest(
        id=request.id,
        occurrence_key=request.occurrence_key,
        target=request.target,
        created_at=request.created_at,
        concurrency_policy=request.concurrency_policy,
        retry_policy=request.retry_policy,
        timeout=request.timeout,
        state=request.state,
        version=request.version,
    )


def _clone_admission_lock(lock: ScheduleAdmissionLock) -> ScheduleAdmissionLock:
    return ScheduleAdmissionLock(
        schedule_id=lock.schedule_id,
        worker_id=lock.worker_id,
        token=lock.token,
        acquired_at=lock.acquired_at,
        expires_at=lock.expires_at,
        generation=lock.generation,
        state=lock.state,
        released_at=lock.released_at,
        version=lock.version,
    )


def _clone_materialization_lease(
    lease: ScheduleMaterializationLease,
) -> ScheduleMaterializationLease:
    return ScheduleMaterializationLease(
        schedule_id=lease.schedule_id,
        worker_id=lease.worker_id,
        token=lease.token,
        acquired_at=lease.acquired_at,
        expires_at=lease.expires_at,
        generation=lease.generation,
        state=lease.state,
        released_at=lease.released_at,
        version=lease.version,
    )


def _clone_claim(claim: ExecutionClaim) -> ExecutionClaim:
    return ExecutionClaim(
        execution_id=claim.execution_id,
        worker_id=claim.worker_id,
        token=claim.token,
        claimed_at=claim.claimed_at,
        expires_at=claim.expires_at,
        generation=claim.generation,
        state=claim.state,
        released_at=claim.released_at,
        version=claim.version,
    )


def _clone_execution(execution: Execution) -> Execution:
    return Execution(
        execution_id=execution.id,
        request_id=execution.request_id,
        target=execution.target,
        created_at=execution.created_at,
        policy_snapshot=execution.policy_snapshot,
        idempotency_key=execution.idempotency_key,
        state=execution.state,
        version=execution.version,
        attempt_count=execution.attempt_count,
        active_attempt_number=execution.active_attempt_number,
        next_attempt_at=execution.next_attempt_at,
        cancellation_requested_at=execution.cancellation_requested_at,
        result=execution.result,
    )


def _clone_outbox_message(message: OutboxMessage) -> OutboxMessage:
    return OutboxMessage(
        message_id=message.id,
        event_type=message.event_type,
        aggregate_type=message.aggregate_type,
        aggregate_id=message.aggregate_id,
        payload=message.payload,
        created_at=message.created_at,
        sequence=message.sequence,
        state=message.state,
        published_at=message.published_at,
        publish_attempts=message.publish_attempts,
        last_error=message.last_error,
        version=message.version,
    )


def _clone_attempt(attempt: Attempt) -> Attempt:
    return Attempt(
        attempt_id=attempt.id,
        execution_id=attempt.execution_id,
        number=attempt.number,
        started_at=attempt.started_at,
        state=attempt.state,
        result=attempt.result,
        version=attempt.version,
    )


class InMemoryStore:
    """Shared committed state backing independent in-memory UnitOfWork instances."""

    def __init__(self) -> None:
        self._schedules: dict[ScheduleId, Schedule] = {}
        self._execution_requests: dict[RequestId, ExecutionRequest] = {}
        self._request_by_occurrence: dict[OccurrenceKey, RequestId] = {}
        self._executions: dict[ExecutionId, Execution] = {}
        self._execution_by_request: dict[RequestId, ExecutionId] = {}
        self._attempts: dict[AttemptId, Attempt] = {}
        self._attempt_by_number: dict[tuple[ExecutionId, int], AttemptId] = {}
        self._admission_locks: dict[ScheduleId, ScheduleAdmissionLock] = {}
        self._materialization_leases: dict[ScheduleId, ScheduleMaterializationLease] = {}
        self._claims: dict[ExecutionId, ExecutionClaim] = {}
        self._outbox_messages: dict[OutboxMessageId, OutboxMessage] = {}
        self._lock = RLock()


InMemoryScheduleStore = InMemoryStore


class InMemoryScheduleRepository:
    """Schedule repository with an identity map and staged write set."""

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store
        self._tracked: dict[ScheduleId, Schedule] = {}
        self._expected_versions: dict[ScheduleId, PersistenceVersion] = {}
        self._new: set[ScheduleId] = set()
        self._dirty: set[ScheduleId] = set()

    def add(self, schedule: Schedule) -> None:
        schedule_id = schedule.id
        if schedule_id in self._tracked:
            raise DuplicateScheduleError(
                f"Schedule {schedule_id.value!r} is already tracked by this UnitOfWork."
            )
        self._tracked[schedule_id] = schedule
        self._new.add(schedule_id)

    def get(self, schedule_id: ScheduleId) -> Schedule | None:
        tracked = self._tracked.get(schedule_id)
        if tracked is not None:
            return tracked

        with self._store._lock:
            committed = self._store._schedules.get(schedule_id)
            if committed is None:
                return None
            loaded = _clone_schedule(committed)
            self._tracked[schedule_id] = loaded
            self._expected_versions[schedule_id] = committed.persistence_version
            return loaded

    def save(self, schedule: Schedule) -> None:
        schedule_id = schedule.id
        tracked = self._tracked.get(schedule_id)
        if tracked is not schedule:
            raise UntrackedScheduleError(
                f"Schedule {schedule_id.value!r} must be loaded by this UnitOfWork before save()."
            )
        if schedule_id in self._new:
            return
        if schedule_id not in self._expected_versions:
            raise UntrackedScheduleError(
                f"Schedule {schedule_id.value!r} has no tracked committed version."
            )
        self._dirty.add(schedule_id)

    def list_due(self, *, now: Instant, limit: int) -> list[Schedule]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        with self._store._lock:
            candidate_ids = set(self._store._schedules)
        candidate_ids.update(self._tracked)

        due: list[Schedule] = []
        for schedule_id in candidate_ids:
            schedule = self._tracked.get(schedule_id)
            if schedule is None:
                schedule = self.get(schedule_id)
            if schedule is None:
                continue
            if schedule.state is not ScheduleState.ACTIVE:
                continue
            if schedule.next_run_time is None or schedule.next_run_time > now:
                continue
            due.append(schedule)

        due.sort(
            key=lambda schedule: (
                schedule.next_run_time.value if schedule.next_run_time is not None else now.value,
                schedule.id.value,
            )
        )
        return due[:limit]

    def next_run_time(self) -> Instant | None:
        with self._store._lock:
            schedules = list(self._store._schedules.values())

        candidates = [
            schedule.next_run_time
            for schedule in schedules
            if schedule.state is ScheduleState.ACTIVE and schedule.next_run_time is not None
        ]
        return min(candidates) if candidates else None

    def _validate_commit_locked(self) -> None:
        for schedule_id in self._new:
            if schedule_id in self._store._schedules:
                raise DuplicateScheduleError(f"Schedule {schedule_id.value!r} already exists.")

        for schedule_id in self._dirty:
            committed = self._store._schedules.get(schedule_id)
            expected = self._expected_versions[schedule_id]
            if committed is None:
                raise OptimisticConcurrencyError(
                    f"Schedule {schedule_id.value!r} was deleted after it was loaded."
                )
            if committed.persistence_version != expected:
                raise OptimisticConcurrencyError(
                    f"Schedule {schedule_id.value!r} changed concurrently: "
                    f"expected version {expected.value}, "
                    f"found {committed.persistence_version.value}."
                )

    def _apply_commit_locked(self) -> None:
        for schedule_id in self._new | self._dirty:
            self._store._schedules[schedule_id] = _clone_schedule(self._tracked[schedule_id])

    def _after_commit(self) -> None:
        for schedule_id in self._new | self._dirty:
            self._expected_versions[schedule_id] = self._tracked[schedule_id].persistence_version
        self._new.clear()
        self._dirty.clear()

    def _rollback(self) -> None:
        self._tracked.clear()
        self._expected_versions.clear()
        self._new.clear()
        self._dirty.clear()


class InMemoryExecutionRequestRepository:
    """ExecutionRequest repository with optimistic state updates."""

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store
        self._tracked: dict[RequestId, ExecutionRequest] = {}
        self._expected_versions: dict[RequestId, int] = {}
        self._new: set[RequestId] = set()
        self._dirty: set[RequestId] = set()
        self._new_by_occurrence: dict[OccurrenceKey, RequestId] = {}

    def add(self, request: ExecutionRequest) -> None:
        if request.id in self._tracked:
            raise DuplicateExecutionRequestError(
                f"ExecutionRequest {request.id.value!r} is already tracked."
            )
        if request.occurrence_key in self._new_by_occurrence:
            raise DuplicateExecutionRequestError(
                "An ExecutionRequest for this OccurrenceKey is already staged."
            )
        self._tracked[request.id] = request
        self._new.add(request.id)
        self._new_by_occurrence[request.occurrence_key] = request.id

    def get(self, request_id: RequestId) -> ExecutionRequest | None:
        tracked = self._tracked.get(request_id)
        if tracked is not None:
            return tracked

        with self._store._lock:
            committed = self._store._execution_requests.get(request_id)
            if committed is None:
                return None
            loaded = _clone_request(committed)
            self._tracked[request_id] = loaded
            self._expected_versions[request_id] = committed.version
            return loaded

    def get_by_occurrence(self, key: OccurrenceKey) -> ExecutionRequest | None:
        staged_id = self._new_by_occurrence.get(key)
        if staged_id is not None:
            return self._tracked[staged_id]

        with self._store._lock:
            committed_id = self._store._request_by_occurrence.get(key)
        if committed_id is None:
            return None
        return self.get(committed_id)

    def save(self, request: ExecutionRequest) -> None:
        tracked = self._tracked.get(request.id)
        if tracked is not request:
            raise UntrackedEntityError(
                f"ExecutionRequest {request.id.value!r} must be loaded before save()."
            )
        if request.id in self._new:
            return
        if request.id not in self._expected_versions:
            raise UntrackedEntityError(
                f"ExecutionRequest {request.id.value!r} has no tracked committed version."
            )
        self._dirty.add(request.id)

    def list_pending(self, *, limit: int) -> list[ExecutionRequest]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        with self._store._lock:
            candidate_ids = set(self._store._execution_requests)
        candidate_ids.update(self._tracked)

        pending: list[ExecutionRequest] = []
        for request_id in candidate_ids:
            request = self._tracked.get(request_id)
            if request is None:
                request = self.get(request_id)
            if request is None or request.state is not ExecutionRequestState.PENDING:
                continue
            pending.append(request)

        pending.sort(
            key=lambda request: (
                request.occurrence_key.scheduled_at.value,
                request.created_at.value,
                request.id.value,
            )
        )
        return pending[:limit]

    def list_admission_candidates(self, *, limit: int) -> list[ExecutionRequest]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        with self._store._lock:
            candidate_ids = set(self._store._execution_requests)
        candidate_ids.update(self._tracked)

        candidates: list[ExecutionRequest] = []
        for request_id in candidate_ids:
            request = self._tracked.get(request_id)
            if request is None:
                request = self.get(request_id)
            if request is None:
                continue
            if request.state not in (
                ExecutionRequestState.PENDING,
                ExecutionRequestState.WAITING_ADMISSION,
            ):
                continue
            candidates.append(request)

        candidates.sort(
            key=lambda request: (
                request.occurrence_key.scheduled_at.value,
                request.created_at.value,
                request.id.value,
            )
        )
        return candidates[:limit]

    def has_pending(self) -> bool:
        return bool(self.list_pending(limit=1))

    def list_for_reconciliation(self, *, limit: int) -> list[ExecutionRequest]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        with self._store._lock:
            committed = [
                _clone_request(request) for request in self._store._execution_requests.values()
            ]

        committed.sort(
            key=lambda item: (
                item.created_at.value,
                item.id.value,
            )
        )
        return committed[:limit]

    def _validate_commit_locked(self) -> None:
        for request_id in self._new:
            request = self._tracked[request_id]
            if request_id in self._store._execution_requests:
                raise DuplicateExecutionRequestError(
                    f"ExecutionRequest {request_id.value!r} already exists."
                )
            if request.occurrence_key in self._store._request_by_occurrence:
                raise DuplicateExecutionRequestError(
                    "An ExecutionRequest for this OccurrenceKey already exists."
                )

        for request_id in self._dirty:
            committed = self._store._execution_requests.get(request_id)
            expected = self._expected_versions[request_id]
            if committed is None:
                raise OptimisticConcurrencyError(
                    f"ExecutionRequest {request_id.value!r} disappeared after load."
                )
            if committed.version != expected:
                raise OptimisticConcurrencyError(
                    f"ExecutionRequest {request_id.value!r} changed concurrently."
                )

    def _apply_commit_locked(self) -> None:
        for request_id in self._new | self._dirty:
            request = self._tracked[request_id]
            self._store._execution_requests[request_id] = _clone_request(request)
            self._store._request_by_occurrence[request.occurrence_key] = request_id

    def _after_commit(self) -> None:
        for request_id in self._new | self._dirty:
            self._expected_versions[request_id] = self._tracked[request_id].version
        self._new.clear()
        self._dirty.clear()
        self._new_by_occurrence.clear()

    def _rollback(self) -> None:
        self._tracked.clear()
        self._expected_versions.clear()
        self._new.clear()
        self._dirty.clear()
        self._new_by_occurrence.clear()


class InMemoryExecutionRepository:
    """Execution repository enforcing one Execution per RequestId."""

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store
        self._tracked: dict[ExecutionId, Execution] = {}
        self._expected_versions: dict[ExecutionId, int] = {}
        self._new: set[ExecutionId] = set()
        self._dirty: set[ExecutionId] = set()
        self._new_by_request: dict[RequestId, ExecutionId] = {}

    def add(self, execution: Execution) -> None:
        if execution.id in self._tracked:
            raise DuplicateExecutionError(f"Execution {execution.id.value!r} is already tracked.")
        if execution.request_id in self._new_by_request:
            raise DuplicateExecutionError("An Execution for this RequestId is already staged.")
        self._tracked[execution.id] = execution
        self._new.add(execution.id)
        self._new_by_request[execution.request_id] = execution.id

    def get(self, execution_id: ExecutionId) -> Execution | None:
        tracked = self._tracked.get(execution_id)
        if tracked is not None:
            return tracked

        with self._store._lock:
            committed = self._store._executions.get(execution_id)
            if committed is None:
                return None
            loaded = _clone_execution(committed)
            self._tracked[execution_id] = loaded
            self._expected_versions[execution_id] = committed.version
            return loaded

    def get_by_request(self, request_id: RequestId) -> Execution | None:
        staged_id = self._new_by_request.get(request_id)
        if staged_id is not None:
            return self._tracked[staged_id]

        with self._store._lock:
            committed_id = self._store._execution_by_request.get(request_id)
        if committed_id is None:
            return None
        return self.get(committed_id)

    def save(self, execution: Execution) -> None:
        tracked = self._tracked.get(execution.id)
        if tracked is not execution:
            raise UntrackedEntityError(
                f"Execution {execution.id.value!r} must be loaded before save()."
            )
        if execution.id in self._new:
            return
        if execution.id not in self._expected_versions:
            raise UntrackedEntityError(
                f"Execution {execution.id.value!r} has no tracked committed version."
            )
        self._dirty.add(execution.id)

    def list_queued(self, *, limit: int) -> list[Execution]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        with self._store._lock:
            candidate_ids = set(self._store._executions)
        candidate_ids.update(self._tracked)

        queued: list[Execution] = []
        for execution_id in candidate_ids:
            execution = self._tracked.get(execution_id)
            if execution is None:
                execution = self.get(execution_id)
            if execution is None or execution.state is not ExecutionState.QUEUED:
                continue
            queued.append(execution)

        with self._store._lock:
            request_scheduled_at = {
                request_id: request.occurrence_key.scheduled_at.value
                for request_id, request in self._store._execution_requests.items()
            }

        queued.sort(
            key=lambda execution: (
                request_scheduled_at.get(
                    execution.request_id,
                    execution.created_at.value,
                ),
                execution.created_at.value,
                execution.id.value,
            )
        )
        return queued[:limit]

    def list_runnable(self, *, now: Instant, limit: int) -> list[Execution]:
        """Return queued Executions and retries whose retry deadline is due."""

        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        with self._store._lock:
            candidate_ids = set(self._store._executions)
            request_scheduled_at = {
                request_id: request.occurrence_key.scheduled_at.value
                for request_id, request in self._store._execution_requests.items()
            }
        candidate_ids.update(self._tracked)

        runnable: list[Execution] = []
        for execution_id in candidate_ids:
            execution = self._tracked.get(execution_id)
            if execution is None:
                execution = self.get(execution_id)
            if execution is None:
                continue
            if execution.state is ExecutionState.QUEUED:
                runnable.append(execution)
                continue
            if (
                execution.state is ExecutionState.RETRY_WAIT
                and execution.next_attempt_at is not None
                and execution.next_attempt_at <= now
            ):
                runnable.append(execution)

        runnable.sort(
            key=lambda execution: (
                execution.next_attempt_at.value
                if execution.state is ExecutionState.RETRY_WAIT
                and execution.next_attempt_at is not None
                else request_scheduled_at.get(
                    execution.request_id,
                    execution.created_at.value,
                ),
                execution.created_at.value,
                execution.id.value,
            )
        )
        return runnable[:limit]

    def list_running(self, *, limit: int) -> list[Execution]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        with self._store._lock:
            committed = [
                _clone_execution(execution)
                for execution in self._store._executions.values()
                if execution.state is ExecutionState.RUNNING
            ]

        committed.sort(key=lambda item: (item.created_at.value, item.id.value))
        return committed[:limit]

    def next_runnable_at(self, *, now: Instant) -> Instant | None:
        with self._store._lock:
            candidate_ids = set(self._store._executions)
        candidate_ids.update(self._tracked)

        executions: list[Execution] = []
        for execution_id in candidate_ids:
            execution = self._tracked.get(execution_id)
            if execution is None:
                execution = self.get(execution_id)
            if execution is not None:
                executions.append(execution)

        if any(execution.state is ExecutionState.QUEUED for execution in executions):
            return now

        retry_times = [
            execution.next_attempt_at
            for execution in executions
            if execution.state is ExecutionState.RETRY_WAIT
            and execution.next_attempt_at is not None
        ]
        if not retry_times:
            return None
        next_retry = min(retry_times)
        return now if next_retry <= now else next_retry

    def list_for_reconciliation(self, *, limit: int) -> list[Execution]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        with self._store._lock:
            committed = [
                _clone_execution(execution) for execution in self._store._executions.values()
            ]

        committed.sort(key=lambda item: (item.created_at.value, item.id.value))
        return committed[:limit]

    def count_non_terminal_for_schedule(self, schedule_id: ScheduleId) -> int:
        with self._store._lock:
            committed_executions = dict(self._store._executions)
            committed_requests = dict(self._store._execution_requests)

        candidate_ids = set(committed_executions)
        candidate_ids.update(self._tracked)

        count = 0
        for execution_id in candidate_ids:
            execution = self._tracked.get(execution_id)
            if execution is None:
                execution = committed_executions.get(execution_id)
            if execution is None or execution.is_terminal:
                continue

            request = committed_requests.get(execution.request_id)
            if request is None:
                continue
            if request.occurrence_key.schedule_id == schedule_id:
                count += 1

        return count

    def _validate_commit_locked(self) -> None:
        for execution_id in self._new:
            execution = self._tracked[execution_id]
            if execution_id in self._store._executions:
                raise DuplicateExecutionError(f"Execution {execution_id.value!r} already exists.")
            if execution.request_id in self._store._execution_by_request:
                raise DuplicateExecutionError("An Execution for this RequestId already exists.")

        for execution_id in self._dirty:
            committed = self._store._executions.get(execution_id)
            expected = self._expected_versions[execution_id]
            if committed is None:
                raise OptimisticConcurrencyError(
                    f"Execution {execution_id.value!r} disappeared after load."
                )
            if committed.version != expected:
                raise OptimisticConcurrencyError(
                    f"Execution {execution_id.value!r} changed concurrently."
                )

    def _apply_commit_locked(self) -> None:
        for execution_id in self._new | self._dirty:
            execution = self._tracked[execution_id]
            self._store._executions[execution_id] = _clone_execution(execution)
            self._store._execution_by_request[execution.request_id] = execution_id

    def _after_commit(self) -> None:
        for execution_id in self._new | self._dirty:
            self._expected_versions[execution_id] = self._tracked[execution_id].version
        self._new.clear()
        self._dirty.clear()
        self._new_by_request.clear()

    def _rollback(self) -> None:
        self._tracked.clear()
        self._expected_versions.clear()
        self._new.clear()
        self._dirty.clear()
        self._new_by_request.clear()


class InMemoryAttemptRepository:
    """Attempt repository enforcing unique number within one Execution."""

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store
        self._tracked: dict[AttemptId, Attempt] = {}
        self._expected_versions: dict[AttemptId, int] = {}
        self._new: set[AttemptId] = set()
        self._dirty: set[AttemptId] = set()

    def add(self, attempt: Attempt) -> None:
        if attempt.id in self._tracked:
            raise DuplicateAttemptError(f"Attempt {attempt.id.value!r} is already tracked.")
        self._tracked[attempt.id] = attempt
        self._new.add(attempt.id)

    def get(self, attempt_id: AttemptId) -> Attempt | None:
        tracked = self._tracked.get(attempt_id)
        if tracked is not None:
            return tracked

        with self._store._lock:
            committed = self._store._attempts.get(attempt_id)
            if committed is None:
                return None
            loaded = _clone_attempt(committed)
            self._tracked[attempt_id] = loaded
            self._expected_versions[attempt_id] = committed.version
            return loaded

    def save(self, attempt: Attempt) -> None:
        tracked = self._tracked.get(attempt.id)
        if tracked is not attempt:
            raise UntrackedEntityError(
                f"Attempt {attempt.id.value!r} must be loaded before save()."
            )
        if attempt.id in self._new:
            return
        if attempt.id not in self._expected_versions:
            raise UntrackedEntityError(
                f"Attempt {attempt.id.value!r} has no tracked committed version."
            )
        self._dirty.add(attempt.id)

    def list_for_execution(self, execution_id: ExecutionId) -> list[Attempt]:
        with self._store._lock:
            committed_ids = [
                attempt_id
                for (candidate_execution_id, _), attempt_id in (
                    self._store._attempt_by_number.items()
                )
                if candidate_execution_id == execution_id
            ]

        result: dict[AttemptId, Attempt] = {}
        for attempt_id in committed_ids:
            attempt = self.get(attempt_id)
            if attempt is not None:
                result[attempt_id] = attempt

        for attempt_id in self._new:
            attempt = self._tracked[attempt_id]
            if attempt.execution_id == execution_id:
                result[attempt_id] = attempt

        return sorted(result.values(), key=lambda attempt: attempt.number)

    def _validate_commit_locked(self) -> None:
        for attempt_id in self._new:
            attempt = self._tracked[attempt_id]
            key = (attempt.execution_id, attempt.number)
            if attempt_id in self._store._attempts:
                raise DuplicateAttemptError(f"Attempt {attempt_id.value!r} already exists.")
            if key in self._store._attempt_by_number:
                raise DuplicateAttemptError(
                    "An Attempt with this execution_id and number already exists."
                )

        for attempt_id in self._dirty:
            committed = self._store._attempts.get(attempt_id)
            expected = self._expected_versions[attempt_id]
            if committed is None:
                raise OptimisticConcurrencyError(
                    f"Attempt {attempt_id.value!r} disappeared after load."
                )
            if committed.version != expected:
                raise OptimisticConcurrencyError(
                    f"Attempt {attempt_id.value!r} changed concurrently."
                )

    def _apply_commit_locked(self) -> None:
        for attempt_id in self._new | self._dirty:
            attempt = self._tracked[attempt_id]
            self._store._attempts[attempt_id] = _clone_attempt(attempt)
            self._store._attempt_by_number[(attempt.execution_id, attempt.number)] = attempt_id

    def _after_commit(self) -> None:
        for attempt_id in self._new | self._dirty:
            self._expected_versions[attempt_id] = self._tracked[attempt_id].version
        self._new.clear()
        self._dirty.clear()

    def _rollback(self) -> None:
        self._tracked.clear()
        self._expected_versions.clear()
        self._new.clear()
        self._dirty.clear()


class InMemoryScheduleAdmissionLockRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store
        self._tracked: dict[ScheduleId, ScheduleAdmissionLock] = {}
        self._expected_versions: dict[ScheduleId, int] = {}
        self._new: set[ScheduleId] = set()
        self._dirty: set[ScheduleId] = set()

    def add(self, lock: ScheduleAdmissionLock) -> None:
        if lock.schedule_id in self._tracked:
            raise DuplicateAdmissionLockError(
                f"ScheduleAdmissionLock {lock.schedule_id.value!r} is already tracked."
            )
        self._tracked[lock.schedule_id] = lock
        self._new.add(lock.schedule_id)

    def get(self, schedule_id: ScheduleId) -> ScheduleAdmissionLock | None:
        tracked = self._tracked.get(schedule_id)
        if tracked is not None:
            return tracked
        with self._store._lock:
            committed = self._store._admission_locks.get(schedule_id)
            if committed is None:
                return None
            loaded = _clone_admission_lock(committed)
            self._tracked[schedule_id] = loaded
            self._expected_versions[schedule_id] = committed.version
            return loaded

    def save(self, lock: ScheduleAdmissionLock) -> None:
        if self._tracked.get(lock.schedule_id) is not lock:
            raise UntrackedEntityError(
                f"ScheduleAdmissionLock {lock.schedule_id.value!r} must be loaded before save()."
            )
        if lock.schedule_id in self._new:
            return
        if lock.schedule_id not in self._expected_versions:
            raise UntrackedEntityError(
                f"ScheduleAdmissionLock {lock.schedule_id.value!r} has no tracked version."
            )
        self._dirty.add(lock.schedule_id)

    def _validate_commit_locked(self) -> None:
        for schedule_id in self._new:
            if schedule_id in self._store._admission_locks:
                raise DuplicateAdmissionLockError(
                    f"ScheduleAdmissionLock {schedule_id.value!r} already exists."
                )
            if schedule_id not in self._store._schedules:
                raise ReferentialIntegrityError(
                    "ScheduleAdmissionLock references a Schedule that does not exist."
                )
        for schedule_id in self._dirty:
            committed = self._store._admission_locks.get(schedule_id)
            expected = self._expected_versions[schedule_id]
            if committed is None or committed.version != expected:
                raise OptimisticConcurrencyError(
                    f"ScheduleAdmissionLock {schedule_id.value!r} changed concurrently."
                )

    def _apply_commit_locked(self) -> None:
        for schedule_id in self._new | self._dirty:
            self._store._admission_locks[schedule_id] = _clone_admission_lock(
                self._tracked[schedule_id]
            )

    def _after_commit(self) -> None:
        for schedule_id in self._new | self._dirty:
            self._expected_versions[schedule_id] = self._tracked[schedule_id].version
        self._new.clear()
        self._dirty.clear()

    def _rollback(self) -> None:
        self._tracked.clear()
        self._expected_versions.clear()
        self._new.clear()
        self._dirty.clear()


class InMemoryScheduleMaterializationLeaseRepository:
    """Schedule materialization lease repository with optimistic version checks."""

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store
        self._tracked: dict[ScheduleId, ScheduleMaterializationLease] = {}
        self._expected_versions: dict[ScheduleId, int] = {}
        self._new: set[ScheduleId] = set()
        self._dirty: set[ScheduleId] = set()

    def add(self, lease: ScheduleMaterializationLease) -> None:
        if lease.schedule_id in self._tracked:
            raise DuplicateMaterializationLeaseError(
                f"ScheduleMaterializationLease {lease.schedule_id.value!r} is already tracked."
            )
        self._tracked[lease.schedule_id] = lease
        self._new.add(lease.schedule_id)

    def get(self, schedule_id: ScheduleId) -> ScheduleMaterializationLease | None:
        tracked = self._tracked.get(schedule_id)
        if tracked is not None:
            return tracked
        with self._store._lock:
            committed = self._store._materialization_leases.get(schedule_id)
            if committed is None:
                return None
            loaded = _clone_materialization_lease(committed)
            self._tracked[schedule_id] = loaded
            self._expected_versions[schedule_id] = committed.version
            return loaded

    def save(self, lease: ScheduleMaterializationLease) -> None:
        if self._tracked.get(lease.schedule_id) is not lease:
            raise UntrackedEntityError(
                f"ScheduleMaterializationLease {lease.schedule_id.value!r} "
                "must be loaded before save()."
            )
        if lease.schedule_id in self._new:
            return
        if lease.schedule_id not in self._expected_versions:
            raise UntrackedEntityError(
                f"ScheduleMaterializationLease {lease.schedule_id.value!r} has no tracked version."
            )
        self._dirty.add(lease.schedule_id)

    def _validate_commit_locked(self) -> None:
        for schedule_id in self._new:
            if schedule_id in self._store._materialization_leases:
                raise DuplicateMaterializationLeaseError(
                    f"ScheduleMaterializationLease {schedule_id.value!r} already exists."
                )
            if schedule_id not in self._store._schedules:
                raise ReferentialIntegrityError(
                    "ScheduleMaterializationLease references a Schedule that does not exist."
                )

        for schedule_id in self._dirty:
            committed = self._store._materialization_leases.get(schedule_id)
            expected = self._expected_versions[schedule_id]
            if committed is None or committed.version != expected:
                raise OptimisticConcurrencyError(
                    f"ScheduleMaterializationLease {schedule_id.value!r} changed concurrently."
                )

    def _apply_commit_locked(self) -> None:
        for schedule_id in self._new | self._dirty:
            self._store._materialization_leases[schedule_id] = _clone_materialization_lease(
                self._tracked[schedule_id]
            )

    def _after_commit(self) -> None:
        for schedule_id in self._new | self._dirty:
            self._expected_versions[schedule_id] = self._tracked[schedule_id].version
        self._new.clear()
        self._dirty.clear()

    def _rollback(self) -> None:
        self._tracked.clear()
        self._expected_versions.clear()
        self._new.clear()
        self._dirty.clear()


class InMemoryExecutionClaimRepository:
    """Execution claim repository with optimistic version checks."""

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store
        self._tracked: dict[ExecutionId, ExecutionClaim] = {}
        self._expected_versions: dict[ExecutionId, int] = {}
        self._new: set[ExecutionId] = set()
        self._dirty: set[ExecutionId] = set()

    def add(self, claim: ExecutionClaim) -> None:
        if claim.execution_id in self._tracked:
            raise DuplicateExecutionClaimError(
                f"ExecutionClaim {claim.execution_id.value!r} is already tracked."
            )
        self._tracked[claim.execution_id] = claim
        self._new.add(claim.execution_id)

    def get(self, execution_id: ExecutionId) -> ExecutionClaim | None:
        tracked = self._tracked.get(execution_id)
        if tracked is not None:
            return tracked

        with self._store._lock:
            committed = self._store._claims.get(execution_id)
            if committed is None:
                return None
            loaded = _clone_claim(committed)
            self._tracked[execution_id] = loaded
            self._expected_versions[execution_id] = committed.version
            return loaded

    def save(self, claim: ExecutionClaim) -> None:
        if self._tracked.get(claim.execution_id) is not claim:
            raise UntrackedEntityError(
                f"ExecutionClaim {claim.execution_id.value!r} must be loaded before save()."
            )
        if claim.execution_id in self._new:
            return
        if claim.execution_id not in self._expected_versions:
            raise UntrackedEntityError(
                f"ExecutionClaim {claim.execution_id.value!r} has no tracked committed version."
            )
        self._dirty.add(claim.execution_id)

    def _validate_commit_locked(self) -> None:
        for execution_id in self._new:
            if execution_id in self._store._claims:
                raise DuplicateExecutionClaimError(
                    f"ExecutionClaim {execution_id.value!r} already exists."
                )
            if execution_id not in self._store._executions:
                raise ReferentialIntegrityError(
                    "ExecutionClaim references an Execution that does not exist."
                )

        for execution_id in self._dirty:
            committed = self._store._claims.get(execution_id)
            expected = self._expected_versions[execution_id]
            if committed is None or committed.version != expected:
                raise OptimisticConcurrencyError(
                    f"ExecutionClaim {execution_id.value!r} changed concurrently."
                )

    def _apply_commit_locked(self) -> None:
        for execution_id in self._new | self._dirty:
            self._store._claims[execution_id] = _clone_claim(self._tracked[execution_id])

    def _after_commit(self) -> None:
        for execution_id in self._new | self._dirty:
            self._expected_versions[execution_id] = self._tracked[execution_id].version
        self._new.clear()
        self._dirty.clear()

    def _rollback(self) -> None:
        self._tracked.clear()
        self._expected_versions.clear()
        self._new.clear()
        self._dirty.clear()


class InMemoryOutboxRepository:
    """Outbox repository preserving staged transactional semantics."""

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store
        self._tracked: dict[OutboxMessageId, OutboxMessage] = {}
        self._expected_versions: dict[OutboxMessageId, int] = {}
        self._new: set[OutboxMessageId] = set()
        self._dirty: set[OutboxMessageId] = set()

    def add(self, message: OutboxMessage) -> None:
        if message.id in self._tracked:
            raise DuplicateOutboxMessageError(
                f"OutboxMessage {message.id.value!r} is already tracked."
            )
        self._tracked[message.id] = message
        self._new.add(message.id)

    def get(self, message_id: OutboxMessageId) -> OutboxMessage | None:
        tracked = self._tracked.get(message_id)
        if tracked is not None:
            return tracked

        with self._store._lock:
            committed = self._store._outbox_messages.get(message_id)
            if committed is None:
                return None
            loaded = _clone_outbox_message(committed)
            self._tracked[message_id] = loaded
            self._expected_versions[message_id] = committed.version
            return loaded

    def save(self, message: OutboxMessage) -> None:
        if self._tracked.get(message.id) is not message:
            raise UntrackedEntityError(
                f"OutboxMessage {message.id.value!r} must be loaded before save()."
            )
        if message.id in self._new:
            return
        if message.id not in self._expected_versions:
            raise UntrackedEntityError(
                f"OutboxMessage {message.id.value!r} has no tracked committed version."
            )
        self._dirty.add(message.id)

    def list_pending(self, *, limit: int) -> list[OutboxMessage]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        with self._store._lock:
            ids = [
                message_id
                for message_id, message in self._store._outbox_messages.items()
                if message.state is OutboxState.PENDING
            ]

        result: list[OutboxMessage] = []
        for message_id in ids:
            message = self.get(message_id)
            if message is not None:
                result.append(message)

        result.sort(
            key=lambda item: (
                item.created_at.value,
                item.aggregate_type,
                item.aggregate_id,
                item.sequence,
                item.id.value,
            )
        )
        return result[:limit]

    def _validate_commit_locked(self) -> None:
        for message_id in self._new:
            if message_id in self._store._outbox_messages:
                raise DuplicateOutboxMessageError(
                    f"OutboxMessage {message_id.value!r} already exists."
                )

        for message_id in self._dirty:
            committed = self._store._outbox_messages.get(message_id)
            expected = self._expected_versions[message_id]
            if committed is None or committed.version != expected:
                raise OptimisticConcurrencyError(
                    f"OutboxMessage {message_id.value!r} changed concurrently."
                )

    def _apply_commit_locked(self) -> None:
        for message_id in self._new | self._dirty:
            self._store._outbox_messages[message_id] = _clone_outbox_message(
                self._tracked[message_id]
            )

    def _after_commit(self) -> None:
        for message_id in self._new | self._dirty:
            self._expected_versions[message_id] = self._tracked[message_id].version
        self._new.clear()
        self._dirty.clear()

    def _rollback(self) -> None:
        self._tracked.clear()
        self._expected_versions.clear()
        self._new.clear()
        self._dirty.clear()


class InMemoryRetentionRepository:
    """Stage bounded cleanup against the shared committed in-memory store."""

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store
        self._criteria: tuple[Instant, Instant, Instant, int] | None = None
        self._result = RetentionCleanupStats()

    def stage_cleanup(
        self,
        *,
        executions_completed_before: Instant,
        orphan_requests_created_before: Instant,
        outbox_published_before: Instant,
        limit: int,
    ) -> None:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")
        self._criteria = (
            executions_completed_before,
            orphan_requests_created_before,
            outbox_published_before,
            limit,
        )
        self._result = RetentionCleanupStats()

    @property
    def result(self) -> RetentionCleanupStats:
        return self._result

    def _validate_commit_locked(self) -> None:
        return

    def _apply_commit_locked(self) -> None:
        if self._criteria is None:
            self._result = RetentionCleanupStats()
            return

        execution_cutoff, request_cutoff, outbox_cutoff, limit = self._criteria
        budget = limit

        execution_candidates = sorted(
            (
                execution
                for execution in self._store._executions.values()
                if execution.is_terminal
                and execution.result is not None
                and execution.result.completed_at < execution_cutoff
            ),
            key=lambda item: (
                (item.result.completed_at.value, item.id.value)
                if item.result is not None
                else (execution_cutoff.value, item.id.value)
            ),
        )[:budget]

        for execution in execution_candidates:
            execution_id = execution.id
            request_id = execution.request_id

            attempt_keys = [key for key in self._store._attempt_by_number if key[0] == execution_id]
            for key in attempt_keys:
                attempt_id = self._store._attempt_by_number.pop(key)
                self._store._attempts.pop(attempt_id, None)

            self._store._claims.pop(execution_id, None)
            self._store._executions.pop(execution_id, None)
            self._store._execution_by_request.pop(request_id, None)

            request = self._store._execution_requests.pop(request_id, None)
            if request is not None:
                self._store._request_by_occurrence.pop(request.occurrence_key, None)

        execution_count = len(execution_candidates)
        budget -= execution_count

        orphan_candidates: list[ExecutionRequest] = []
        if budget > 0:
            orphan_candidates = sorted(
                (
                    request
                    for request in self._store._execution_requests.values()
                    if request.state
                    in (
                        ExecutionRequestState.DROPPED,
                        ExecutionRequestState.CANCELLED,
                    )
                    and request.created_at < request_cutoff
                    and request.id not in self._store._execution_by_request
                ),
                key=lambda item: (item.created_at.value, item.id.value),
            )[:budget]

            for request in orphan_candidates:
                self._store._execution_requests.pop(request.id, None)
                self._store._request_by_occurrence.pop(request.occurrence_key, None)

            budget -= len(orphan_candidates)

        outbox_candidates: list[OutboxMessage] = []
        if budget > 0:
            outbox_candidates = sorted(
                (
                    message
                    for message in self._store._outbox_messages.values()
                    if message.state is OutboxState.PUBLISHED
                    and message.published_at is not None
                    and message.published_at < outbox_cutoff
                ),
                key=lambda item: (
                    item.published_at.value
                    if item.published_at is not None
                    else outbox_cutoff.value,
                    item.id.value,
                ),
            )[:budget]

            for message in outbox_candidates:
                self._store._outbox_messages.pop(message.id, None)

        self._result = RetentionCleanupStats(
            execution_graphs=execution_count,
            orphan_requests=len(orphan_candidates),
            published_outbox_messages=len(outbox_candidates),
        )

    def _after_commit(self) -> None:
        self._criteria = None

    def _rollback(self) -> None:
        self._criteria = None
        self._result = RetentionCleanupStats()


class InMemoryUnitOfWork:
    """Explicit transaction across scheduling and execution repositories."""

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store
        self._active = False

        self._schedules = InMemoryScheduleRepository(store)
        self._requests = InMemoryExecutionRequestRepository(store)
        self._executions = InMemoryExecutionRepository(store)
        self._attempts = InMemoryAttemptRepository(store)
        self._admission_locks = InMemoryScheduleAdmissionLockRepository(store)
        self._materialization_leases = InMemoryScheduleMaterializationLeaseRepository(store)
        self._claims = InMemoryExecutionClaimRepository(store)
        self._outbox = InMemoryOutboxRepository(store)
        self._retention = InMemoryRetentionRepository(store)

        self.schedules: ScheduleRepository = self._schedules
        self.requests: ExecutionRequestRepository = self._requests
        self.executions: ExecutionRepository = self._executions
        self.attempts: AttemptRepository = self._attempts
        self.admission_locks: ScheduleAdmissionLockRepository = self._admission_locks
        self.materialization_leases: ScheduleMaterializationLeaseRepository = (
            self._materialization_leases
        )
        self.claims: ExecutionClaimRepository = self._claims
        self.outbox: OutboxRepository = self._outbox
        self.retention: RetentionRepository = self._retention

    def __enter__(self) -> UnitOfWork:
        if self._active:
            raise RuntimeError("UnitOfWork is already active.")
        self._active = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        self.rollback()
        self._active = False

    def _validate_referential_integrity_locked(self) -> None:
        schedule_ids = set(self._store._schedules)
        schedule_ids.update(self._schedules._new)
        for request_id in self._requests._new:
            request = self._requests._tracked[request_id]
            if request.occurrence_key.schedule_id not in schedule_ids:
                raise ReferentialIntegrityError(
                    "ExecutionRequest references a Schedule that does not exist."
                )

        request_ids = set(self._store._execution_requests)
        request_ids.update(self._requests._new)
        for execution_id in self._executions._new:
            execution = self._executions._tracked[execution_id]
            if execution.request_id not in request_ids:
                raise ReferentialIntegrityError(
                    "Execution references an ExecutionRequest that does not exist."
                )

        execution_ids = set(self._store._executions)
        execution_ids.update(self._executions._new)
        for attempt_id in self._attempts._new:
            attempt = self._attempts._tracked[attempt_id]
            if attempt.execution_id not in execution_ids:
                raise ReferentialIntegrityError(
                    "Attempt references an Execution that does not exist."
                )

    def commit(self) -> None:
        self._require_active()
        repositories = (
            self._schedules,
            self._requests,
            self._executions,
            self._attempts,
            self._admission_locks,
            self._materialization_leases,
            self._claims,
            self._outbox,
            self._retention,
        )

        with self._store._lock:
            self._validate_referential_integrity_locked()
            for repository in repositories:
                repository._validate_commit_locked()
            for repository in repositories:
                repository._apply_commit_locked()
            for repository in repositories:
                repository._after_commit()

    def rollback(self) -> None:
        self._schedules._rollback()
        self._requests._rollback()
        self._executions._rollback()
        self._attempts._rollback()
        self._admission_locks._rollback()
        self._materialization_leases._rollback()
        self._claims._rollback()
        self._outbox._rollback()
        self._retention._rollback()

    def _require_active(self) -> None:
        if not self._active:
            raise RuntimeError("UnitOfWork must be entered before commit().")


class InMemoryUnitOfWorkFactory:
    """Factory sharing one committed store across independent transactions."""

    def __init__(self, store: InMemoryStore | None = None) -> None:
        self._store = store or InMemoryStore()

    def __call__(self) -> UnitOfWork:
        return InMemoryUnitOfWork(self._store)
