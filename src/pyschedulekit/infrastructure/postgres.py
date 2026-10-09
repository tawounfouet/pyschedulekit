"""Internal PostgreSQL core persistence adapter.

PG-01 intentionally implements only the four core repositories. It is not exported through
the stable public API and must not be wired into Scheduler until PG-02/PG-03 complete the
full UnitOfWork contract.
"""

from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Any, NoReturn, cast

import psycopg
from psycopg import Connection, Cursor, IntegrityError
from psycopg.rows import dict_row

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
from pyschedulekit.domain.occurrence import OccurrenceKey
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
    DuplicateAttemptError,
    DuplicateExecutionError,
    DuplicateExecutionRequestError,
    DuplicateScheduleError,
    ExecutionRepository,
    ExecutionRequestRepository,
    OptimisticConcurrencyError,
    PersistenceConflictError,
    ReferentialIntegrityError,
    ScheduleRepository,
    UntrackedEntityError,
    UntrackedScheduleError,
)

PostgresRow = dict[str, Any]
PostgresConnection = Connection[PostgresRow]


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
            None if row["active_attempt_number"] is None else cast(int, row["active_attempt_number"])
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
        for schedule_id in self._new:
            row = self._connection.execute(
                "SELECT 1 FROM schedules WHERE id = %s",
                (schedule_id.value,),
            ).fetchone()
            if row is not None:
                raise DuplicateScheduleError(f"Schedule {schedule_id.value!r} already exists.")

        for schedule_id in self._dirty:
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
        for schedule_id in self._new:
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

        for schedule_id in self._dirty:
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
        for schedule_id in self._new | self._dirty:
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
        for request_id in self._new:
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

        for request_id in self._dirty:
            row = self._connection.execute(
                "SELECT version FROM execution_requests WHERE id = %s",
                (request_id.value,),
            ).fetchone()
            if row is None or cast(int, row["version"]) != self._expected_versions[request_id]:
                raise OptimisticConcurrencyError(
                    f"ExecutionRequest {request_id.value!r} changed concurrently."
                )

    def _apply(self) -> None:
        for request_id in self._new:
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

        for request_id in self._dirty:
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
            if execution.state is ExecutionState.RETRY_WAIT and execution.next_attempt_at is not None:
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
        for execution_id in self._new:
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

        for execution_id in self._dirty:
            row = self._connection.execute(
                "SELECT version FROM executions WHERE id = %s",
                (execution_id.value,),
            ).fetchone()
            if row is None or cast(int, row["version"]) != self._expected_versions[execution_id]:
                raise OptimisticConcurrencyError(
                    f"Execution {execution_id.value!r} changed concurrently."
                )

    def _apply(self) -> None:
        for execution_id in self._new:
            self._insert(self._tracked[execution_id])
        for execution_id in self._dirty:
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
            raise UntrackedEntityError(f"Attempt {attempt.id.value!r} must be loaded before save().")
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
        for attempt_id in self._new:
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

        for attempt_id in self._dirty:
            row = self._connection.execute(
                "SELECT version FROM attempts WHERE id = %s",
                (attempt_id.value,),
            ).fetchone()
            if row is None or cast(int, row["version"]) != self._expected_versions[attempt_id]:
                raise OptimisticConcurrencyError(
                    f"Attempt {attempt_id.value!r} changed concurrently."
                )

    def _apply(self) -> None:
        for attempt_id in self._new:
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

        for attempt_id in self._dirty:
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
        for attempt_id in self._new | self._dirty:
            self._expected_versions[attempt_id] = self._tracked[attempt_id].version
        self._new.clear()
        self._dirty.clear()

    def _rollback(self) -> None:
        self._tracked.clear()
        self._expected_versions.clear()
        self._new.clear()
        self._dirty.clear()


class PostgresCoreUnitOfWork:
    """PG-01 UnitOfWork for the four core repositories only."""

    def __init__(self, connection: PostgresConnection) -> None:
        self._connection = connection
        self._active = False

        self._schedules = PostgresScheduleRepository(connection)
        self._requests = PostgresExecutionRequestRepository(connection)
        self._executions = PostgresExecutionRepository(connection)
        self._attempts = PostgresAttemptRepository(connection)

        self.schedules: ScheduleRepository = self._schedules
        self.requests: ExecutionRequestRepository = self._requests
        self.executions: ExecutionRepository = self._executions
        self.attempts: AttemptRepository = self._attempts

    def __enter__(self) -> PostgresCoreUnitOfWork:
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
        self._connection.close()

    def commit(self) -> None:
        self._require_active()
        repositories = (
            self._schedules,
            self._requests,
            self._executions,
            self._attempts,
        )
        try:
            for repository in repositories:
                repository._validate()
            for repository in repositories:
                repository._apply()
            self._connection.commit()
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

    def _require_active(self) -> None:
        if not self._active:
            raise RuntimeError("UnitOfWork must be entered before commit().")


class PostgresCoreUnitOfWorkFactory:
    """Internal PG-01 factory for core repository qualification."""

    def __init__(self, dsn: str) -> None:
        if not dsn.strip():
            raise ValueError("PostgreSQL DSN must not be empty.")
        self._dsn = dsn

        with psycopg.connect(self._dsn, autocommit=True, row_factory=dict_row) as connection:
            initialize_postgres_schema(cast(PostgresConnection, connection))

    def __call__(self) -> PostgresCoreUnitOfWork:
        connection = psycopg.connect(
            self._dsn,
            autocommit=False,
            row_factory=dict_row,
        )
        return PostgresCoreUnitOfWork(cast(PostgresConnection, connection))
