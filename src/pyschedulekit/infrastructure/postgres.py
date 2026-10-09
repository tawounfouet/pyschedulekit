"""Internal PostgreSQL persistence adapter.

PG-01 introduced the four core repositories. PG-02 adds coordination, outbox and retention
repositories plus a full UnitOfWork. The adapter remains internal until PG-03 parity and
PG-04 Scheduler/multi-worker qualification complete.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Any, NoReturn, Protocol, TypeVar, cast

import psycopg
from psycopg import Connection, Cursor, IntegrityError, IsolationLevel
from psycopg.errors import DeadlockDetected, SerializationFailure
from psycopg.rows import dict_row

from pyschedulekit.domain.admission_lock import (
    AdmissionToken,
    ScheduleAdmissionLock,
    ScheduleAdmissionLockState,
)
from pyschedulekit.domain.claim import (
    ClaimToken,
    ExecutionClaim,
    ExecutionClaimState,
    WorkerId,
)
from pyschedulekit.domain.execution import (
    Attempt,
    AttemptId,
    AttemptState,
    Execution,
    ExecutionId,
    ExecutionState,
    IdempotencyKey,
)
from pyschedulekit.domain.execution_request import (
    ExecutionRequest,
    ExecutionRequestState,
    RequestId,
)
from pyschedulekit.domain.materialization_lease import (
    MaterializationToken,
    ScheduleMaterializationLease,
    ScheduleMaterializationLeaseState,
)
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.outbox import OutboxMessage, OutboxMessageId, OutboxState
from pyschedulekit.domain.schedule import (
    PersistenceVersion,
    Schedule,
    ScheduleId,
    ScheduleRevision,
    ScheduleState,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.infrastructure.postgres_schema import initialize_postgres_schema
from pyschedulekit.infrastructure.sql_codec import (
    decode_attempt_result,
    decode_concurrency_policy,
    decode_execution_policy_snapshot,
    decode_execution_result,
    decode_retry_policy,
    decode_schedule_definition,
    encode_attempt_result,
    encode_concurrency_policy,
    encode_execution_policy_snapshot,
    encode_execution_result,
    encode_retry_policy,
    encode_schedule_definition,
)
from pyschedulekit.ports.persistence import (
    AttemptRepository,
    DatabaseInvariantError,
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
    PersistenceConflictError,
    ReferentialIntegrityError,
    RetentionCleanupStats,
    RetentionRepository,
    ScheduleAdmissionLockRepository,
    ScheduleMaterializationLeaseRepository,
    ScheduleRepository,
    TransientPersistenceError,
    UnitOfWork,
    UntrackedEntityError,
    UntrackedScheduleError,
)

PostgresRow = dict[str, Any]
PostgresConnection = Connection[PostgresRow]
PostgresConnectionProvider = Callable[[], PostgresConnection]
PostgresConnectionReleaser = Callable[[PostgresConnection], None]


class _StringIdentity(Protocol):
    @property
    def value(self) -> str: ...


IdentityT = TypeVar("IdentityT", bound=_StringIdentity)


def _ordered_ids(values: set[IdentityT]) -> list[IdentityT]:
    """Return staged identities in one deterministic database-lock order."""

    return sorted(values, key=lambda item: item.value)


def _optional_instant(value: object) -> Instant | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return Instant(value)
    return Instant.parse(str(value))


def _optional_duration(value: object) -> Duration | None:
    if value is None:
        return None
    return Duration.seconds(float(cast(int | float, value)))


def _raise_integrity_error(exc: IntegrityError) -> NoReturn:
    constraint = exc.diag.constraint_name or ""
    table = exc.diag.table_name or ""
    sqlstate = exc.sqlstate

    if sqlstate == "23505":
        if table == "schedules" or constraint == "schedules_pkey":
            raise DuplicateScheduleError("Schedule identity already exists.") from exc
        if table == "execution_requests" or constraint.startswith("execution_requests_"):
            raise DuplicateExecutionRequestError(
                "ExecutionRequest identity or OccurrenceKey already exists."
            ) from exc
        if table == "executions" or constraint.startswith("executions_"):
            raise DuplicateExecutionError(
                "Execution identity, RequestId, or idempotency key already exists."
            ) from exc
        if table == "attempts" or constraint.startswith("attempts_"):
            raise DuplicateAttemptError(
                "Attempt identity or execution attempt number already exists."
            ) from exc
        if table == "schedule_admission_locks":
            raise DuplicateAdmissionLockError(
                "Schedule admission lock identity or token already exists."
            ) from exc
        if table == "schedule_materialization_leases":
            raise DuplicateMaterializationLeaseError(
                "Schedule materialization lease identity or token already exists."
            ) from exc
        if table == "execution_claims":
            raise DuplicateExecutionClaimError(
                "Execution claim identity or token already exists."
            ) from exc
        if table == "outbox_messages":
            raise DuplicateOutboxMessageError("Outbox message identity already exists.") from exc

    if sqlstate == "23503":
        raise ReferentialIntegrityError(
            "PostgreSQL rejected a scheduler write because a referenced record does not exist."
        ) from exc

    if sqlstate == "23514":
        raise DatabaseInvariantError(
            "PostgreSQL rejected a scheduler write because a database invariant failed."
        ) from exc

    raise PersistenceConflictError("PostgreSQL rejected a scheduler persistence write.") from exc


def _require_cas_update(cursor: Cursor[PostgresRow], *, entity: str) -> None:
    if cursor.rowcount != 1:
        raise OptimisticConcurrencyError(
            f"{entity} changed concurrently before the compare-and-swap update."
        )


def _schedule_from_row(row: PostgresRow) -> Schedule:
    return Schedule(
        schedule_id=ScheduleId(str(row["id"])),
        definition=decode_schedule_definition(str(row["definition_json"])),
        state=ScheduleState(str(row["state"])),
        revision=ScheduleRevision(cast(int, row["revision"])),
        persistence_version=PersistenceVersion(cast(int, row["persistence_version"])),
        next_run_time=_optional_instant(row["next_run_time"]),
    )


def _request_from_row(row: PostgresRow) -> ExecutionRequest:
    return ExecutionRequest(
        id=RequestId(str(row["id"])),
        occurrence_key=OccurrenceKey(
            schedule_id=ScheduleId(str(row["schedule_id"])),
            schedule_revision=ScheduleRevision(cast(int, row["schedule_revision"])),
            scheduled_at=cast(Instant, _optional_instant(row["scheduled_at"])),
        ),
        target=TargetRef(
            kind=str(row["target_kind"]),
            reference=str(row["target_reference"]),
        ),
        created_at=cast(Instant, _optional_instant(row["created_at"])),
        concurrency_policy=decode_concurrency_policy(str(row["concurrency_json"])),
        retry_policy=decode_retry_policy(str(row["retry_json"])),
        timeout=_optional_duration(row["timeout_seconds"]),
        state=ExecutionRequestState(str(row["state"])),
        version=cast(int, row["version"]),
    )


def _execution_from_row(row: PostgresRow) -> Execution:
    return Execution(
        execution_id=ExecutionId(str(row["id"])),
        request_id=RequestId(str(row["request_id"])),
        target=TargetRef(
            kind=str(row["target_kind"]),
            reference=str(row["target_reference"]),
        ),
        created_at=cast(Instant, _optional_instant(row["created_at"])),
        policy_snapshot=decode_execution_policy_snapshot(str(row["policy_json"])),
        idempotency_key=IdempotencyKey(str(row["idempotency_key"])),
        state=ExecutionState(str(row["state"])),
        version=cast(int, row["version"]),
        attempt_count=cast(int, row["attempt_count"]),
        active_attempt_number=(
            None
            if row["active_attempt_number"] is None
            else cast(int, row["active_attempt_number"])
        ),
        next_attempt_at=_optional_instant(row["next_attempt_at"]),
        cancellation_requested_at=_optional_instant(row["cancellation_requested_at"]),
        result=decode_execution_result(
            None if row["result_json"] is None else str(row["result_json"])
        ),
    )


def _attempt_from_row(row: PostgresRow) -> Attempt:
    return Attempt(
        attempt_id=AttemptId(str(row["id"])),
        execution_id=ExecutionId(str(row["execution_id"])),
        number=cast(int, row["number"]),
        started_at=cast(Instant, _optional_instant(row["started_at"])),
        state=AttemptState(str(row["state"])),
        result=decode_attempt_result(
            None if row["result_json"] is None else str(row["result_json"])
        ),
        version=cast(int, row["version"]),
    )


def _admission_lock_from_row(row: PostgresRow) -> ScheduleAdmissionLock:
    return ScheduleAdmissionLock(
        schedule_id=ScheduleId(str(row["schedule_id"])),
        worker_id=WorkerId(str(row["worker_id"])),
        token=AdmissionToken(str(row["token"])),
        acquired_at=cast(Instant, _optional_instant(row["acquired_at"])),
        expires_at=cast(Instant, _optional_instant(row["expires_at"])),
        generation=cast(int, row["generation"]),
        state=ScheduleAdmissionLockState(str(row["state"])),
        released_at=_optional_instant(row["released_at"]),
        version=cast(int, row["version"]),
    )


def _materialization_lease_from_row(row: PostgresRow) -> ScheduleMaterializationLease:
    return ScheduleMaterializationLease(
        schedule_id=ScheduleId(str(row["schedule_id"])),
        worker_id=WorkerId(str(row["worker_id"])),
        token=MaterializationToken(str(row["token"])),
        acquired_at=cast(Instant, _optional_instant(row["acquired_at"])),
        expires_at=cast(Instant, _optional_instant(row["expires_at"])),
        generation=cast(int, row["generation"]),
        state=ScheduleMaterializationLeaseState(str(row["state"])),
        released_at=_optional_instant(row["released_at"]),
        version=cast(int, row["version"]),
    )


def _claim_from_row(row: PostgresRow) -> ExecutionClaim:
    return ExecutionClaim(
        execution_id=ExecutionId(str(row["execution_id"])),
        worker_id=WorkerId(str(row["worker_id"])),
        token=ClaimToken(str(row["token"])),
        claimed_at=cast(Instant, _optional_instant(row["claimed_at"])),
        expires_at=cast(Instant, _optional_instant(row["expires_at"])),
        generation=cast(int, row["generation"]),
        state=ExecutionClaimState(str(row["state"])),
        released_at=_optional_instant(row["released_at"]),
        version=cast(int, row["version"]),
    )


def _encode_outbox_payload(payload: tuple[tuple[str, str], ...]) -> str:
    return json.dumps(dict(payload), separators=(",", ":"), sort_keys=True)


def _decode_outbox_payload(value: str) -> tuple[tuple[str, str], ...]:
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise ValueError("Persisted outbox payload must be a JSON object.")
    return tuple(sorted((str(key), str(item)) for key, item in decoded.items()))


def _outbox_from_row(row: PostgresRow) -> OutboxMessage:
    return OutboxMessage(
        message_id=OutboxMessageId(str(row["id"])),
        event_type=str(row["event_type"]),
        aggregate_type=str(row["aggregate_type"]),
        aggregate_id=str(row["aggregate_id"]),
        payload=_decode_outbox_payload(str(row["payload_json"])),
        created_at=cast(Instant, _optional_instant(row["created_at"])),
        sequence=cast(int, row["sequence"]),
        state=OutboxState(str(row["state"])),
        published_at=_optional_instant(row["published_at"]),
        publish_attempts=cast(int, row["publish_attempts"]),
        last_error=None if row["last_error"] is None else str(row["last_error"]),
        version=cast(int, row["version"]),
    )


class PostgresScheduleRepository:
    def __init__(self, connection: PostgresConnection) -> None:
        self._connection = connection
        self._tracked: dict[ScheduleId, Schedule] = {}
        self._expected_versions: dict[ScheduleId, PersistenceVersion] = {}
        self._new: set[ScheduleId] = set()
        self._dirty: set[ScheduleId] = set()

    def add(self, schedule: Schedule) -> None:
        if schedule.id in self._tracked:
            raise DuplicateScheduleError(
                f"Schedule {schedule.id.value!r} is already tracked by this UnitOfWork."
            )
        self._tracked[schedule.id] = schedule
        self._new.add(schedule.id)

    def get(self, schedule_id: ScheduleId) -> Schedule | None:
        tracked = self._tracked.get(schedule_id)
        if tracked is not None:
            return tracked

        row = self._connection.execute(
            "SELECT * FROM schedules WHERE id = %s",
            (schedule_id.value,),
        ).fetchone()
        if row is None:
            return None

        loaded = _schedule_from_row(row)
        self._tracked[schedule_id] = loaded
        self._expected_versions[schedule_id] = loaded.persistence_version
        return loaded

    def save(self, schedule: Schedule) -> None:
        if self._tracked.get(schedule.id) is not schedule:
            raise UntrackedScheduleError(
                f"Schedule {schedule.id.value!r} must be loaded by this UnitOfWork before save()."
            )
        if schedule.id in self._new:
            return
        if schedule.id not in self._expected_versions:
            raise UntrackedScheduleError(
                f"Schedule {schedule.id.value!r} has no tracked committed version."
            )
        self._dirty.add(schedule.id)

    def list_due(self, *, now: Instant, limit: int) -> list[Schedule]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        ids = {
            ScheduleId(str(row["id"]))
            for row in self._connection.execute("SELECT id FROM schedules").fetchall()
        }
        ids.update(self._tracked)

        due: list[Schedule] = []
        for schedule_id in ids:
            schedule = self._tracked.get(schedule_id) or self.get(schedule_id)
            if schedule is None or schedule.state is not ScheduleState.ACTIVE:
                continue
            if schedule.next_run_time is None or schedule.next_run_time > now:
                continue
            due.append(schedule)

        due.sort(
            key=lambda item: (
                item.next_run_time.value if item.next_run_time is not None else now.value,
                item.id.value,
            )
        )
        return due[:limit]

    def next_run_time(self) -> Instant | None:
        ids = {
            ScheduleId(str(row["id"]))
            for row in self._connection.execute("SELECT id FROM schedules").fetchall()
        }
        ids.update(self._tracked)

        candidates: list[Instant] = []
        for schedule_id in ids:
            schedule = self._tracked.get(schedule_id) or self.get(schedule_id)
            if (
                schedule is not None
                and schedule.state is ScheduleState.ACTIVE
                and schedule.next_run_time is not None
            ):
                candidates.append(schedule.next_run_time)
        return min(candidates) if candidates else None

    def _validate(self) -> None:
        for schedule_id in _ordered_ids(self._new):
            row = self._connection.execute(
                "SELECT 1 FROM schedules WHERE id = %s",
                (schedule_id.value,),
            ).fetchone()
            if row is not None:
                raise DuplicateScheduleError(f"Schedule {schedule_id.value!r} already exists.")

        for schedule_id in _ordered_ids(self._dirty):
            row = self._connection.execute(
                "SELECT persistence_version FROM schedules WHERE id = %s",
                (schedule_id.value,),
            ).fetchone()
            expected = self._expected_versions[schedule_id]
            if row is None or cast(int, row["persistence_version"]) != expected.value:
                raise OptimisticConcurrencyError(
                    f"Schedule {schedule_id.value!r} changed concurrently."
                )

    def _apply(self) -> None:
        for schedule_id in _ordered_ids(self._new):
            schedule = self._tracked[schedule_id]
            self._connection.execute(
                """
                INSERT INTO schedules(
                    id, definition_json, state, revision,
                    persistence_version, next_run_time
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    schedule.id.value,
                    encode_schedule_definition(schedule.definition),
                    schedule.state.value,
                    schedule.revision.value,
                    schedule.persistence_version.value,
                    None if schedule.next_run_time is None else schedule.next_run_time.value,
                ),
            )

        for schedule_id in _ordered_ids(self._dirty):
            schedule = self._tracked[schedule_id]
            expected = self._expected_versions[schedule_id]
            cursor = self._connection.execute(
                """
                UPDATE schedules
                SET definition_json = %s, state = %s, revision = %s,
                    persistence_version = %s, next_run_time = %s
                WHERE id = %s AND persistence_version = %s
                """,
                (
                    encode_schedule_definition(schedule.definition),
                    schedule.state.value,
                    schedule.revision.value,
                    schedule.persistence_version.value,
                    None if schedule.next_run_time is None else schedule.next_run_time.value,
                    schedule.id.value,
                    expected.value,
                ),
            )
            _require_cas_update(cursor, entity=f"Schedule {schedule.id.value!r}")

    def _after_commit(self) -> None:
        for schedule_id in _ordered_ids(self._new | self._dirty):
            self._expected_versions[schedule_id] = self._tracked[schedule_id].persistence_version
        self._new.clear()
        self._dirty.clear()

    def _rollback(self) -> None:
        self._tracked.clear()
        self._expected_versions.clear()
        self._new.clear()
        self._dirty.clear()


class PostgresExecutionRequestRepository:
    def __init__(self, connection: PostgresConnection) -> None:
        self._connection = connection
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
        row = self._connection.execute(
            "SELECT * FROM execution_requests WHERE id = %s",
            (request_id.value,),
        ).fetchone()
        if row is None:
            return None
        loaded = _request_from_row(row)
        self._tracked[request_id] = loaded
        self._expected_versions[request_id] = loaded.version
        return loaded

    def get_by_occurrence(self, key: OccurrenceKey) -> ExecutionRequest | None:
        staged_id = self._new_by_occurrence.get(key)
        if staged_id is not None:
            return self._tracked[staged_id]
        row = self._connection.execute(
            """
            SELECT id
            FROM execution_requests
            WHERE schedule_id = %s AND schedule_revision = %s AND scheduled_at = %s
            ORDER BY id
            LIMIT 1
            """,
            (
                key.schedule_id.value,
                key.schedule_revision.value,
                key.scheduled_at.value,
            ),
        ).fetchone()
        return None if row is None else self.get(RequestId(str(row["id"])))

    def save(self, request: ExecutionRequest) -> None:
        if self._tracked.get(request.id) is not request:
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
        return self._list_states((ExecutionRequestState.PENDING,), limit=limit)

    def list_admission_candidates(self, *, limit: int) -> list[ExecutionRequest]:
        return self._list_states(
            (ExecutionRequestState.PENDING, ExecutionRequestState.WAITING_ADMISSION),
            limit=limit,
        )

    def has_pending(self) -> bool:
        return bool(self.list_pending(limit=1))

    def list_for_reconciliation(self, *, limit: int) -> list[ExecutionRequest]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")
        rows = self._connection.execute(
            """
            SELECT id
            FROM execution_requests
            ORDER BY created_at, id
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
        result: list[ExecutionRequest] = []
        for row in rows:
            request = self.get(RequestId(str(row["id"])))
            if request is not None:
                result.append(request)
        return result

    def _list_states(
        self,
        states: tuple[ExecutionRequestState, ...],
        *,
        limit: int,
    ) -> list[ExecutionRequest]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        ids = {
            RequestId(str(row["id"]))
            for row in self._connection.execute("SELECT id FROM execution_requests").fetchall()
        }
        ids.update(self._tracked)

        candidates: list[ExecutionRequest] = []
        for request_id in ids:
            request = self._tracked.get(request_id) or self.get(request_id)
            if request is not None and request.state in states:
                candidates.append(request)

        candidates.sort(
            key=lambda item: (
                item.occurrence_key.scheduled_at.value,
                item.created_at.value,
                item.id.value,
            )
        )
        return candidates[:limit]

    def _validate(self) -> None:
        for request_id in _ordered_ids(self._new):
            request = self._tracked[request_id]
            if (
                self._connection.execute(
                    "SELECT 1 FROM execution_requests WHERE id = %s",
                    (request_id.value,),
                ).fetchone()
                is not None
            ):
                raise DuplicateExecutionRequestError(
                    f"ExecutionRequest {request_id.value!r} already exists."
                )

            if (
                self._connection.execute(
                    """
                    SELECT 1
                    FROM execution_requests
                    WHERE schedule_id = %s AND schedule_revision = %s AND scheduled_at = %s
                    LIMIT 1
                    """,
                    (
                        request.occurrence_key.schedule_id.value,
                        request.occurrence_key.schedule_revision.value,
                        request.occurrence_key.scheduled_at.value,
                    ),
                ).fetchone()
                is not None
            ):
                raise DuplicateExecutionRequestError(
                    "An ExecutionRequest for this OccurrenceKey already exists."
                )

        for request_id in _ordered_ids(self._dirty):
            row = self._connection.execute(
                "SELECT version FROM execution_requests WHERE id = %s",
                (request_id.value,),
            ).fetchone()
            if row is None or cast(int, row["version"]) != self._expected_versions[request_id]:
                raise OptimisticConcurrencyError(
                    f"ExecutionRequest {request_id.value!r} changed concurrently."
                )

    def _apply(self) -> None:
        for request_id in _ordered_ids(self._new):
            request = self._tracked[request_id]
            self._connection.execute(
                """
                INSERT INTO execution_requests(
                    id, schedule_id, schedule_revision, scheduled_at,
                    target_kind, target_reference, created_at,
                    concurrency_json, retry_json, timeout_seconds,
                    state, version
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    request.id.value,
                    request.occurrence_key.schedule_id.value,
                    request.occurrence_key.schedule_revision.value,
                    request.occurrence_key.scheduled_at.value,
                    request.target.kind,
                    request.target.reference,
                    request.created_at.value,
                    encode_concurrency_policy(request.concurrency_policy),
                    encode_retry_policy(request.retry_policy),
                    None if request.timeout is None else request.timeout.total_seconds,
                    request.state.value,
                    request.version,
                ),
            )

        for request_id in _ordered_ids(self._dirty):
            request = self._tracked[request_id]
            expected = self._expected_versions[request_id]
            cursor = self._connection.execute(
                """
                UPDATE execution_requests
                SET schedule_id = %s, schedule_revision = %s, scheduled_at = %s,
                    target_kind = %s, target_reference = %s, created_at = %s,
                    concurrency_json = %s, retry_json = %s, timeout_seconds = %s,
                    state = %s, version = %s
                WHERE id = %s AND version = %s
                """,
                (
                    request.occurrence_key.schedule_id.value,
                    request.occurrence_key.schedule_revision.value,
                    request.occurrence_key.scheduled_at.value,
                    request.target.kind,
                    request.target.reference,
                    request.created_at.value,
                    encode_concurrency_policy(request.concurrency_policy),
                    encode_retry_policy(request.retry_policy),
                    None if request.timeout is None else request.timeout.total_seconds,
                    request.state.value,
                    request.version,
                    request.id.value,
                    expected,
                ),
            )
            _require_cas_update(cursor, entity=f"ExecutionRequest {request.id.value!r}")

    def _after_commit(self) -> None:
        for request_id in _ordered_ids(self._new | self._dirty):
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


class PostgresExecutionRepository:
    def __init__(self, connection: PostgresConnection) -> None:
        self._connection = connection
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
        row = self._connection.execute(
            "SELECT * FROM executions WHERE id = %s",
            (execution_id.value,),
        ).fetchone()
        if row is None:
            return None
        loaded = _execution_from_row(row)
        self._tracked[execution_id] = loaded
        self._expected_versions[execution_id] = loaded.version
        return loaded

    def get_by_request(self, request_id: RequestId) -> Execution | None:
        staged = self._new_by_request.get(request_id)
        if staged is not None:
            return self._tracked[staged]
        row = self._connection.execute(
            "SELECT id FROM executions WHERE request_id = %s ORDER BY id LIMIT 1",
            (request_id.value,),
        ).fetchone()
        return None if row is None else self.get(ExecutionId(str(row["id"])))

    def save(self, execution: Execution) -> None:
        if self._tracked.get(execution.id) is not execution:
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
        return self._list_states(states=(ExecutionState.QUEUED,), now=None, limit=limit)

    def list_runnable(self, *, now: Instant, limit: int) -> list[Execution]:
        return self._list_states(
            states=(ExecutionState.QUEUED, ExecutionState.RETRY_WAIT),
            now=now,
            limit=limit,
        )

    def _list_states(
        self,
        *,
        states: tuple[ExecutionState, ...],
        now: Instant | None,
        limit: int,
    ) -> list[Execution]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        ids = {
            ExecutionId(str(row["id"]))
            for row in self._connection.execute("SELECT id FROM executions").fetchall()
        }
        ids.update(self._tracked)

        runnable: list[Execution] = []
        for execution_id in ids:
            execution = self._tracked.get(execution_id) or self.get(execution_id)
            if execution is None or execution.state not in states:
                continue
            if execution.state is ExecutionState.RETRY_WAIT and (
                now is None or execution.next_attempt_at is None or execution.next_attempt_at > now
            ):
                continue
            runnable.append(execution)

        def sort_key(execution: Execution) -> tuple[object, ...]:
            scheduled = self._request_scheduled_at(execution.request_id)
            primary = (
                execution.next_attempt_at.value
                if execution.state is ExecutionState.RETRY_WAIT
                and execution.next_attempt_at is not None
                else scheduled.value
                if scheduled is not None
                else execution.created_at.value
            )
            return (primary, execution.created_at.value, execution.id.value)

        runnable.sort(key=sort_key)
        return runnable[:limit]

    def list_running(self, *, limit: int) -> list[Execution]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")
        rows = self._connection.execute(
            """
            SELECT id
            FROM executions
            WHERE state = %s
            ORDER BY created_at, id
            LIMIT %s
            """,
            (ExecutionState.RUNNING.value, limit),
        ).fetchall()
        result: list[Execution] = []
        for row in rows:
            execution = self.get(ExecutionId(str(row["id"])))
            if execution is not None:
                result.append(execution)
        return result

    def next_runnable_at(self, *, now: Instant) -> Instant | None:
        ids = {
            ExecutionId(str(row["id"]))
            for row in self._connection.execute("SELECT id FROM executions").fetchall()
        }
        ids.update(self._tracked)

        retries: list[Instant] = []
        for execution_id in ids:
            execution = self._tracked.get(execution_id) or self.get(execution_id)
            if execution is None:
                continue
            if execution.state is ExecutionState.QUEUED:
                return now
            if (
                execution.state is ExecutionState.RETRY_WAIT
                and execution.next_attempt_at is not None
            ):
                retries.append(execution.next_attempt_at)

        if not retries:
            return None
        next_retry = min(retries)
        return now if next_retry <= now else next_retry

    def list_for_reconciliation(self, *, limit: int) -> list[Execution]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")
        rows = self._connection.execute(
            """
            SELECT id
            FROM executions
            ORDER BY created_at, id
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
        result: list[Execution] = []
        for row in rows:
            execution = self.get(ExecutionId(str(row["id"])))
            if execution is not None:
                result.append(execution)
        return result

    def count_non_terminal_for_schedule(self, schedule_id: ScheduleId) -> int:
        ids = {
            ExecutionId(str(row["id"]))
            for row in self._connection.execute("SELECT id FROM executions").fetchall()
        }
        ids.update(self._tracked)

        count = 0
        for execution_id in ids:
            execution = self._tracked.get(execution_id) or self.get(execution_id)
            if execution is None or execution.is_terminal:
                continue
            if self._request_schedule_id(execution.request_id) == schedule_id:
                count += 1
        return count

    def _request_scheduled_at(self, request_id: RequestId) -> Instant | None:
        row = self._connection.execute(
            "SELECT scheduled_at FROM execution_requests WHERE id = %s",
            (request_id.value,),
        ).fetchone()
        return None if row is None else _optional_instant(row["scheduled_at"])

    def _request_schedule_id(self, request_id: RequestId) -> ScheduleId | None:
        row = self._connection.execute(
            "SELECT schedule_id FROM execution_requests WHERE id = %s",
            (request_id.value,),
        ).fetchone()
        return None if row is None else ScheduleId(str(row["schedule_id"]))

    def _validate(self) -> None:
        for execution_id in _ordered_ids(self._new):
            execution = self._tracked[execution_id]
            if (
                self._connection.execute(
                    "SELECT 1 FROM executions WHERE id = %s",
                    (execution_id.value,),
                ).fetchone()
                is not None
            ):
                raise DuplicateExecutionError(f"Execution {execution_id.value!r} already exists.")

            if (
                self._connection.execute(
                    "SELECT 1 FROM executions WHERE request_id = %s LIMIT 1",
                    (execution.request_id.value,),
                ).fetchone()
                is not None
            ):
                raise DuplicateExecutionError("An Execution for this RequestId already exists.")

        for execution_id in _ordered_ids(self._dirty):
            row = self._connection.execute(
                "SELECT version FROM executions WHERE id = %s",
                (execution_id.value,),
            ).fetchone()
            if row is None or cast(int, row["version"]) != self._expected_versions[execution_id]:
                raise OptimisticConcurrencyError(
                    f"Execution {execution_id.value!r} changed concurrently."
                )

    def _apply(self) -> None:
        for execution_id in _ordered_ids(self._new):
            self._insert(self._tracked[execution_id])
        for execution_id in _ordered_ids(self._dirty):
            self._update(self._tracked[execution_id])

    def _insert(self, execution: Execution) -> None:
        self._connection.execute(
            """
            INSERT INTO executions(
                id, request_id, target_kind, target_reference, created_at,
                policy_json, idempotency_key, state, version, attempt_count,
                active_attempt_number, next_attempt_at,
                cancellation_requested_at, result_json, completed_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            """,
            self._values(execution),
        )

    def _update(self, execution: Execution) -> None:
        values = self._values(execution)
        expected = self._expected_versions[execution.id]
        cursor = self._connection.execute(
            """
            UPDATE executions
            SET request_id = %s, target_kind = %s, target_reference = %s,
                created_at = %s, policy_json = %s, idempotency_key = %s,
                state = %s, version = %s, attempt_count = %s,
                active_attempt_number = %s, next_attempt_at = %s,
                cancellation_requested_at = %s, result_json = %s, completed_at = %s
            WHERE id = %s AND version = %s
            """,
            (*values[1:], values[0], expected),
        )
        _require_cas_update(cursor, entity=f"Execution {execution.id.value!r}")

    @staticmethod
    def _values(execution: Execution) -> tuple[object, ...]:
        return (
            execution.id.value,
            execution.request_id.value,
            execution.target.kind,
            execution.target.reference,
            execution.created_at.value,
            encode_execution_policy_snapshot(execution.policy_snapshot),
            execution.idempotency_key.value,
            execution.state.value,
            execution.version,
            execution.attempt_count,
            execution.active_attempt_number,
            None if execution.next_attempt_at is None else execution.next_attempt_at.value,
            (
                None
                if execution.cancellation_requested_at is None
                else execution.cancellation_requested_at.value
            ),
            encode_execution_result(execution.result),
            execution.result.completed_at.value if execution.result is not None else None,
        )

    def _after_commit(self) -> None:
        for execution_id in _ordered_ids(self._new | self._dirty):
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


class PostgresAttemptRepository:
    def __init__(self, connection: PostgresConnection) -> None:
        self._connection = connection
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
        row = self._connection.execute(
            "SELECT * FROM attempts WHERE id = %s",
            (attempt_id.value,),
        ).fetchone()
        if row is None:
            return None
        loaded = _attempt_from_row(row)
        self._tracked[attempt_id] = loaded
        self._expected_versions[attempt_id] = loaded.version
        return loaded

    def save(self, attempt: Attempt) -> None:
        if self._tracked.get(attempt.id) is not attempt:
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
        ids = {
            AttemptId(str(row["id"]))
            for row in self._connection.execute(
                "SELECT id FROM attempts WHERE execution_id = %s",
                (execution_id.value,),
            ).fetchall()
        }
        ids.update(
            attempt_id
            for attempt_id in self._new
            if self._tracked[attempt_id].execution_id == execution_id
        )
        attempts = [
            attempt
            for attempt_id in ids
            if (attempt := self._tracked.get(attempt_id) or self.get(attempt_id)) is not None
        ]
        attempts.sort(key=lambda item: item.number)
        return attempts

    def _validate(self) -> None:
        for attempt_id in _ordered_ids(self._new):
            attempt = self._tracked[attempt_id]
            if (
                self._connection.execute(
                    "SELECT 1 FROM attempts WHERE id = %s",
                    (attempt_id.value,),
                ).fetchone()
                is not None
            ):
                raise DuplicateAttemptError(f"Attempt {attempt_id.value!r} already exists.")

            if (
                self._connection.execute(
                    """
                    SELECT 1
                    FROM attempts
                    WHERE execution_id = %s AND number = %s
                    LIMIT 1
                    """,
                    (attempt.execution_id.value, attempt.number),
                ).fetchone()
                is not None
            ):
                raise DuplicateAttemptError(
                    "An Attempt with this execution_id and number already exists."
                )

        for attempt_id in _ordered_ids(self._dirty):
            row = self._connection.execute(
                "SELECT version FROM attempts WHERE id = %s",
                (attempt_id.value,),
            ).fetchone()
            if row is None or cast(int, row["version"]) != self._expected_versions[attempt_id]:
                raise OptimisticConcurrencyError(
                    f"Attempt {attempt_id.value!r} changed concurrently."
                )

    def _apply(self) -> None:
        for attempt_id in _ordered_ids(self._new):
            attempt = self._tracked[attempt_id]
            self._connection.execute(
                """
                INSERT INTO attempts(
                    id, execution_id, number, started_at,
                    state, result_json, version
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    attempt.id.value,
                    attempt.execution_id.value,
                    attempt.number,
                    attempt.started_at.value,
                    attempt.state.value,
                    encode_attempt_result(attempt.result),
                    attempt.version,
                ),
            )

        for attempt_id in _ordered_ids(self._dirty):
            attempt = self._tracked[attempt_id]
            expected = self._expected_versions[attempt_id]
            cursor = self._connection.execute(
                """
                UPDATE attempts
                SET execution_id = %s, number = %s, started_at = %s,
                    state = %s, result_json = %s, version = %s
                WHERE id = %s AND version = %s
                """,
                (
                    attempt.execution_id.value,
                    attempt.number,
                    attempt.started_at.value,
                    attempt.state.value,
                    encode_attempt_result(attempt.result),
                    attempt.version,
                    attempt.id.value,
                    expected,
                ),
            )
            _require_cas_update(cursor, entity=f"Attempt {attempt.id.value!r}")

    def _after_commit(self) -> None:
        for attempt_id in _ordered_ids(self._new | self._dirty):
            self._expected_versions[attempt_id] = self._tracked[attempt_id].version
        self._new.clear()
        self._dirty.clear()

    def _rollback(self) -> None:
        self._tracked.clear()
        self._expected_versions.clear()
        self._new.clear()
        self._dirty.clear()


class PostgresScheduleAdmissionLockRepository:
    def __init__(self, connection: PostgresConnection) -> None:
        self._connection = connection
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
        row = self._connection.execute(
            "SELECT * FROM schedule_admission_locks WHERE schedule_id = %s",
            (schedule_id.value,),
        ).fetchone()
        if row is None:
            return None
        loaded = _admission_lock_from_row(row)
        self._tracked[schedule_id] = loaded
        self._expected_versions[schedule_id] = loaded.version
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

    def _validate(self) -> None:
        for schedule_id in _ordered_ids(self._new):
            if (
                self._connection.execute(
                    "SELECT 1 FROM schedule_admission_locks WHERE schedule_id = %s",
                    (schedule_id.value,),
                ).fetchone()
                is not None
            ):
                raise DuplicateAdmissionLockError(
                    f"ScheduleAdmissionLock {schedule_id.value!r} already exists."
                )
        for schedule_id in _ordered_ids(self._dirty):
            row = self._connection.execute(
                "SELECT version FROM schedule_admission_locks WHERE schedule_id = %s",
                (schedule_id.value,),
            ).fetchone()
            if row is None or cast(int, row["version"]) != self._expected_versions[schedule_id]:
                raise OptimisticConcurrencyError(
                    f"ScheduleAdmissionLock {schedule_id.value!r} changed concurrently."
                )

    def _apply(self) -> None:
        for schedule_id in _ordered_ids(self._new):
            lock = self._tracked[schedule_id]
            self._connection.execute(
                """
                INSERT INTO schedule_admission_locks(
                    schedule_id, worker_id, token, acquired_at, expires_at,
                    generation, state, released_at, version
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    lock.schedule_id.value,
                    lock.worker_id.value,
                    lock.token.value,
                    lock.acquired_at.value,
                    lock.expires_at.value,
                    lock.generation,
                    lock.state.value,
                    None if lock.released_at is None else lock.released_at.value,
                    lock.version,
                ),
            )

        for schedule_id in _ordered_ids(self._dirty):
            lock = self._tracked[schedule_id]
            expected = self._expected_versions[schedule_id]
            cursor = self._connection.execute(
                """
                UPDATE schedule_admission_locks
                SET worker_id = %s, token = %s, acquired_at = %s, expires_at = %s,
                    generation = %s, state = %s, released_at = %s, version = %s
                WHERE schedule_id = %s AND version = %s
                """,
                (
                    lock.worker_id.value,
                    lock.token.value,
                    lock.acquired_at.value,
                    lock.expires_at.value,
                    lock.generation,
                    lock.state.value,
                    None if lock.released_at is None else lock.released_at.value,
                    lock.version,
                    lock.schedule_id.value,
                    expected,
                ),
            )
            _require_cas_update(cursor, entity=f"ScheduleAdmissionLock {lock.schedule_id.value!r}")

    def _after_commit(self) -> None:
        for schedule_id in _ordered_ids(self._new | self._dirty):
            self._expected_versions[schedule_id] = self._tracked[schedule_id].version
        self._new.clear()
        self._dirty.clear()

    def _rollback(self) -> None:
        self._tracked.clear()
        self._expected_versions.clear()
        self._new.clear()
        self._dirty.clear()


class PostgresScheduleMaterializationLeaseRepository:
    def __init__(self, connection: PostgresConnection) -> None:
        self._connection = connection
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
        row = self._connection.execute(
            "SELECT * FROM schedule_materialization_leases WHERE schedule_id = %s",
            (schedule_id.value,),
        ).fetchone()
        if row is None:
            return None
        loaded = _materialization_lease_from_row(row)
        self._tracked[schedule_id] = loaded
        self._expected_versions[schedule_id] = loaded.version
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

    def _validate(self) -> None:
        for schedule_id in _ordered_ids(self._new):
            if (
                self._connection.execute(
                    "SELECT 1 FROM schedule_materialization_leases WHERE schedule_id = %s",
                    (schedule_id.value,),
                ).fetchone()
                is not None
            ):
                raise DuplicateMaterializationLeaseError(
                    f"ScheduleMaterializationLease {schedule_id.value!r} already exists."
                )
        for schedule_id in _ordered_ids(self._dirty):
            row = self._connection.execute(
                "SELECT version FROM schedule_materialization_leases WHERE schedule_id = %s",
                (schedule_id.value,),
            ).fetchone()
            if row is None or cast(int, row["version"]) != self._expected_versions[schedule_id]:
                raise OptimisticConcurrencyError(
                    f"ScheduleMaterializationLease {schedule_id.value!r} changed concurrently."
                )

    def _apply(self) -> None:
        for schedule_id in _ordered_ids(self._new):
            lease = self._tracked[schedule_id]
            self._connection.execute(
                """
                INSERT INTO schedule_materialization_leases(
                    schedule_id, worker_id, token, acquired_at, expires_at,
                    generation, state, released_at, version
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    lease.schedule_id.value,
                    lease.worker_id.value,
                    lease.token.value,
                    lease.acquired_at.value,
                    lease.expires_at.value,
                    lease.generation,
                    lease.state.value,
                    None if lease.released_at is None else lease.released_at.value,
                    lease.version,
                ),
            )

        for schedule_id in _ordered_ids(self._dirty):
            lease = self._tracked[schedule_id]
            expected = self._expected_versions[schedule_id]
            cursor = self._connection.execute(
                """
                UPDATE schedule_materialization_leases
                SET worker_id = %s, token = %s, acquired_at = %s, expires_at = %s,
                    generation = %s, state = %s, released_at = %s, version = %s
                WHERE schedule_id = %s AND version = %s
                """,
                (
                    lease.worker_id.value,
                    lease.token.value,
                    lease.acquired_at.value,
                    lease.expires_at.value,
                    lease.generation,
                    lease.state.value,
                    None if lease.released_at is None else lease.released_at.value,
                    lease.version,
                    lease.schedule_id.value,
                    expected,
                ),
            )
            _require_cas_update(
                cursor,
                entity=f"ScheduleMaterializationLease {lease.schedule_id.value!r}",
            )

    def _after_commit(self) -> None:
        for schedule_id in _ordered_ids(self._new | self._dirty):
            self._expected_versions[schedule_id] = self._tracked[schedule_id].version
        self._new.clear()
        self._dirty.clear()

    def _rollback(self) -> None:
        self._tracked.clear()
        self._expected_versions.clear()
        self._new.clear()
        self._dirty.clear()


class PostgresExecutionClaimRepository:
    def __init__(self, connection: PostgresConnection) -> None:
        self._connection = connection
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
        row = self._connection.execute(
            "SELECT * FROM execution_claims WHERE execution_id = %s",
            (execution_id.value,),
        ).fetchone()
        if row is None:
            return None
        loaded = _claim_from_row(row)
        self._tracked[execution_id] = loaded
        self._expected_versions[execution_id] = loaded.version
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

    def _validate(self) -> None:
        for execution_id in _ordered_ids(self._new):
            if (
                self._connection.execute(
                    "SELECT 1 FROM execution_claims WHERE execution_id = %s",
                    (execution_id.value,),
                ).fetchone()
                is not None
            ):
                raise DuplicateExecutionClaimError(
                    f"ExecutionClaim {execution_id.value!r} already exists."
                )
        for execution_id in _ordered_ids(self._dirty):
            row = self._connection.execute(
                "SELECT version FROM execution_claims WHERE execution_id = %s",
                (execution_id.value,),
            ).fetchone()
            if row is None or cast(int, row["version"]) != self._expected_versions[execution_id]:
                raise OptimisticConcurrencyError(
                    f"ExecutionClaim {execution_id.value!r} changed concurrently."
                )

    def _apply(self) -> None:
        for execution_id in _ordered_ids(self._new):
            claim = self._tracked[execution_id]
            self._connection.execute(
                """
                INSERT INTO execution_claims(
                    execution_id, worker_id, token, claimed_at, expires_at,
                    generation, state, released_at, version
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    claim.execution_id.value,
                    claim.worker_id.value,
                    claim.token.value,
                    claim.claimed_at.value,
                    claim.expires_at.value,
                    claim.generation,
                    claim.state.value,
                    None if claim.released_at is None else claim.released_at.value,
                    claim.version,
                ),
            )

        for execution_id in _ordered_ids(self._dirty):
            claim = self._tracked[execution_id]
            expected = self._expected_versions[execution_id]
            cursor = self._connection.execute(
                """
                UPDATE execution_claims
                SET worker_id = %s, token = %s, claimed_at = %s, expires_at = %s,
                    generation = %s, state = %s, released_at = %s, version = %s
                WHERE execution_id = %s AND version = %s
                """,
                (
                    claim.worker_id.value,
                    claim.token.value,
                    claim.claimed_at.value,
                    claim.expires_at.value,
                    claim.generation,
                    claim.state.value,
                    None if claim.released_at is None else claim.released_at.value,
                    claim.version,
                    claim.execution_id.value,
                    expected,
                ),
            )
            _require_cas_update(cursor, entity=f"ExecutionClaim {claim.execution_id.value!r}")

    def _after_commit(self) -> None:
        for execution_id in _ordered_ids(self._new | self._dirty):
            self._expected_versions[execution_id] = self._tracked[execution_id].version
        self._new.clear()
        self._dirty.clear()

    def _rollback(self) -> None:
        self._tracked.clear()
        self._expected_versions.clear()
        self._new.clear()
        self._dirty.clear()


class PostgresOutboxRepository:
    def __init__(self, connection: PostgresConnection) -> None:
        self._connection = connection
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
        row = self._connection.execute(
            "SELECT * FROM outbox_messages WHERE id = %s",
            (message_id.value,),
        ).fetchone()
        if row is None:
            return None
        loaded = _outbox_from_row(row)
        self._tracked[message_id] = loaded
        self._expected_versions[message_id] = loaded.version
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
        rows = self._connection.execute(
            """
            SELECT id
            FROM outbox_messages
            WHERE state = %s
            ORDER BY created_at, aggregate_type, aggregate_id, sequence, id
            LIMIT %s
            """,
            (OutboxState.PENDING.value, limit),
        ).fetchall()
        result: list[OutboxMessage] = []
        for row in rows:
            message = self.get(OutboxMessageId(str(row["id"])))
            if message is not None:
                result.append(message)
        return result

    def _validate(self) -> None:
        for message_id in _ordered_ids(self._new):
            if (
                self._connection.execute(
                    "SELECT 1 FROM outbox_messages WHERE id = %s",
                    (message_id.value,),
                ).fetchone()
                is not None
            ):
                raise DuplicateOutboxMessageError(
                    f"OutboxMessage {message_id.value!r} already exists."
                )
        for message_id in _ordered_ids(self._dirty):
            row = self._connection.execute(
                "SELECT version FROM outbox_messages WHERE id = %s",
                (message_id.value,),
            ).fetchone()
            if row is None or cast(int, row["version"]) != self._expected_versions[message_id]:
                raise OptimisticConcurrencyError(
                    f"OutboxMessage {message_id.value!r} changed concurrently."
                )

    def _apply(self) -> None:
        for message_id in _ordered_ids(self._new):
            message = self._tracked[message_id]
            self._connection.execute(
                """
                INSERT INTO outbox_messages(
                    id, event_type, aggregate_type, aggregate_id,
                    payload_json, created_at, sequence, state, published_at,
                    publish_attempts, last_error, version
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    message.id.value,
                    message.event_type,
                    message.aggregate_type,
                    message.aggregate_id,
                    _encode_outbox_payload(message.payload),
                    message.created_at.value,
                    message.sequence,
                    message.state.value,
                    None if message.published_at is None else message.published_at.value,
                    message.publish_attempts,
                    message.last_error,
                    message.version,
                ),
            )

        for message_id in _ordered_ids(self._dirty):
            message = self._tracked[message_id]
            expected = self._expected_versions[message_id]
            cursor = self._connection.execute(
                """
                UPDATE outbox_messages
                SET event_type = %s, aggregate_type = %s, aggregate_id = %s,
                    payload_json = %s, created_at = %s, sequence = %s, state = %s,
                    published_at = %s, publish_attempts = %s,
                    last_error = %s, version = %s
                WHERE id = %s AND version = %s
                """,
                (
                    message.event_type,
                    message.aggregate_type,
                    message.aggregate_id,
                    _encode_outbox_payload(message.payload),
                    message.created_at.value,
                    message.sequence,
                    message.state.value,
                    None if message.published_at is None else message.published_at.value,
                    message.publish_attempts,
                    message.last_error,
                    message.version,
                    message.id.value,
                    expected,
                ),
            )
            _require_cas_update(cursor, entity=f"OutboxMessage {message.id.value!r}")

    def _after_commit(self) -> None:
        for message_id in _ordered_ids(self._new | self._dirty):
            self._expected_versions[message_id] = self._tracked[message_id].version
        self._new.clear()
        self._dirty.clear()

    def _rollback(self) -> None:
        self._tracked.clear()
        self._expected_versions.clear()
        self._new.clear()
        self._dirty.clear()


class PostgresRetentionRepository:
    def __init__(self, connection: PostgresConnection) -> None:
        self._connection = connection
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

    def _validate(self) -> None:
        return

    def _apply(self) -> None:
        if self._criteria is None:
            self._result = RetentionCleanupStats()
            return

        execution_cutoff, request_cutoff, outbox_cutoff, limit = self._criteria
        budget = limit

        execution_rows = self._connection.execute(
            """
            SELECT id, request_id
            FROM executions
            WHERE state IN ('success', 'failed', 'cancelled', 'timed_out')
              AND completed_at IS NOT NULL
              AND completed_at < %s
            ORDER BY completed_at, id
            LIMIT %s
            """,
            (execution_cutoff.value, budget),
        ).fetchall()

        execution_count = 0
        for row in execution_rows:
            execution_id = str(row["id"])
            request_id = str(row["request_id"])
            self._connection.execute(
                "DELETE FROM attempts WHERE execution_id = %s",
                (execution_id,),
            )
            self._connection.execute(
                "DELETE FROM execution_claims WHERE execution_id = %s",
                (execution_id,),
            )
            deleted = self._connection.execute(
                """
                DELETE FROM executions
                WHERE id = %s
                  AND state IN ('success', 'failed', 'cancelled', 'timed_out')
                  AND completed_at IS NOT NULL
                  AND completed_at < %s
                """,
                (execution_id, execution_cutoff.value),
            )
            if deleted.rowcount != 1:
                continue
            self._connection.execute(
                """
                DELETE FROM execution_requests
                WHERE id = %s
                  AND state = 'dispatched'
                  AND NOT EXISTS (
                      SELECT 1 FROM executions WHERE request_id = %s
                  )
                """,
                (request_id, request_id),
            )
            execution_count += 1

        budget -= execution_count

        orphan_count = 0
        if budget > 0:
            request_rows = self._connection.execute(
                """
                SELECT id
                FROM execution_requests
                WHERE state IN ('dropped', 'cancelled')
                  AND created_at < %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM executions
                      WHERE executions.request_id = execution_requests.id
                  )
                ORDER BY created_at, id
                LIMIT %s
                """,
                (request_cutoff.value, budget),
            ).fetchall()
            for row in request_rows:
                deleted = self._connection.execute(
                    """
                    DELETE FROM execution_requests
                    WHERE id = %s
                      AND state IN ('dropped', 'cancelled')
                      AND created_at < %s
                      AND NOT EXISTS (
                          SELECT 1 FROM executions
                          WHERE executions.request_id = execution_requests.id
                      )
                    """,
                    (str(row["id"]), request_cutoff.value),
                )
                orphan_count += deleted.rowcount

            budget -= orphan_count

        outbox_count = 0
        if budget > 0:
            outbox_rows = self._connection.execute(
                """
                SELECT id
                FROM outbox_messages
                WHERE state = 'published'
                  AND published_at IS NOT NULL
                  AND published_at < %s
                ORDER BY published_at, id
                LIMIT %s
                """,
                (outbox_cutoff.value, budget),
            ).fetchall()
            for row in outbox_rows:
                deleted = self._connection.execute(
                    """
                    DELETE FROM outbox_messages
                    WHERE id = %s
                      AND state = 'published'
                      AND published_at IS NOT NULL
                      AND published_at < %s
                    """,
                    (str(row["id"]), outbox_cutoff.value),
                )
                outbox_count += deleted.rowcount

        self._result = RetentionCleanupStats(
            execution_graphs=execution_count,
            orphan_requests=orphan_count,
            published_outbox_messages=outbox_count,
        )

    def _after_commit(self) -> None:
        self._criteria = None

    def _rollback(self) -> None:
        self._criteria = None
        self._result = RetentionCleanupStats()


class PostgresUnitOfWork:
    """Full internal PostgreSQL UnitOfWork implementing every persistence repository."""

    def __init__(
        self,
        connection: PostgresConnection,
        *,
        release_connection: PostgresConnectionReleaser | None = None,
    ) -> None:
        self._connection = connection
        self._release_connection = release_connection or (lambda item: item.close())
        self._active = False

        self._schedules = PostgresScheduleRepository(connection)
        self._requests = PostgresExecutionRequestRepository(connection)
        self._executions = PostgresExecutionRepository(connection)
        self._attempts = PostgresAttemptRepository(connection)
        self._admission_locks = PostgresScheduleAdmissionLockRepository(connection)
        self._materialization_leases = PostgresScheduleMaterializationLeaseRepository(connection)
        self._claims = PostgresExecutionClaimRepository(connection)
        self._outbox = PostgresOutboxRepository(connection)
        self._retention = PostgresRetentionRepository(connection)

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
        try:
            self.rollback()
        finally:
            self._active = False
            self._release_connection(self._connection)

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
        try:
            for repository in repositories:
                repository._validate()
            for repository in repositories:
                repository._apply()
            self._connection.commit()
        except (DeadlockDetected, SerializationFailure) as exc:
            self._connection.rollback()
            raise TransientPersistenceError(
                "PostgreSQL aborted the transaction because of a transient concurrency "
                "conflict. Retry the whole application operation in a fresh UnitOfWork."
            ) from exc
        except IntegrityError as exc:
            self._connection.rollback()
            _raise_integrity_error(exc)
        except Exception:
            self._connection.rollback()
            raise

        for repository in repositories:
            repository._after_commit()

    def rollback(self) -> None:
        self._connection.rollback()
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


class PostgresUnitOfWorkFactory:
    """Internal PostgreSQL factory; public exposure waits for PG-05 hardening."""

    def __init__(
        self,
        dsn: str,
        *,
        connection_provider: PostgresConnectionProvider | None = None,
        connection_releaser: PostgresConnectionReleaser | None = None,
    ) -> None:
        if not dsn.strip():
            raise ValueError("PostgreSQL DSN must not be empty.")
        if connection_releaser is not None and connection_provider is None:
            raise ValueError("connection_releaser requires connection_provider.")

        self._dsn = dsn
        self._connection_provider = connection_provider
        self._connection_releaser = connection_releaser

        with psycopg.connect(self._dsn, autocommit=True) as connection:
            initialize_postgres_schema(connection)

    def __call__(self) -> UnitOfWork:
        connection = (
            self._connection_provider()
            if self._connection_provider is not None
            else psycopg.connect(
                self._dsn,
                autocommit=False,
                row_factory=dict_row,
            )
        )
        connection.autocommit = False
        connection.isolation_level = IsolationLevel.READ_COMMITTED
        connection.row_factory = dict_row

        return PostgresUnitOfWork(
            connection,
            release_connection=self._connection_releaser,
        )
