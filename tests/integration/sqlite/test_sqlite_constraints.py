"""LOT-22 integration tests for SQLite transaction and constraint hardening."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleRevision,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure.sql_codec import encode_schedule_definition
from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory
from pyschedulekit.ports.persistence import ReferentialIntegrityError


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _schedule(schedule_id: str) -> Schedule:
    return Schedule.create(
        schedule_id=ScheduleId(schedule_id),
        definition=ScheduleDefinition(
            target=TargetRef.python(f"jobs:{schedule_id}"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(),
            ),
        ),
        reference=_instant(hour=9),
    )


def _request(
    *,
    request_id: str,
    schedule_id: str,
) -> ExecutionRequest:
    return ExecutionRequest(
        id=RequestId(request_id),
        occurrence_key=OccurrenceKey(
            schedule_id=ScheduleId(schedule_id),
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        ),
        target=TargetRef.python("jobs:target"),
        created_at=_instant(),
    )


def _raw(database) -> sqlite3.Connection:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def test_t_sql_constraints_001_foreign_key_violation_maps_to_port_error(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)

    with factory() as uow:
        uow.requests.add(
            _request(
                request_id="orphan-request",
                schedule_id="missing-schedule",
            )
        )
        with pytest.raises(ReferentialIntegrityError):
            uow.commit()


def test_t_sql_constraints_002_failed_multi_repository_commit_is_atomic(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)

    with factory() as uow:
        uow.schedules.add(_schedule("valid-schedule"))
        uow.requests.add(
            _request(
                request_id="orphan-request",
                schedule_id="missing-schedule",
            )
        )
        with pytest.raises(ReferentialIntegrityError):
            uow.commit()

    with factory() as observer:
        assert observer.schedules.get(ScheduleId("valid-schedule")) is None
        assert observer.requests.get(RequestId("orphan-request")) is None


def test_t_sql_constraints_003_occurrence_natural_key_is_unique_in_database(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    SqliteUnitOfWorkFactory(database)

    connection = _raw(database)
    try:
        connection.execute(
            """
            INSERT INTO schedules(
                id, definition_json, state, revision,
                persistence_version, next_run_time
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "schedule-a",
                "{}",
                "active",
                1,
                0,
                _instant().value.isoformat(),
            ),
        )
        values = (
            "schedule-a",
            1,
            _instant().value.isoformat(),
            "python",
            "jobs:target",
            _instant().value.isoformat(),
            "{}",
            "{}",
            None,
            "pending",
            0,
        )
        connection.execute(
            """
            INSERT INTO execution_requests(
                id, schedule_id, schedule_revision, scheduled_at,
                target_kind, target_reference, created_at,
                concurrency_json, retry_json, timeout_seconds,
                state, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("request-a", *values),
        )

        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
            connection.execute(
                """
                INSERT INTO execution_requests(
                    id, schedule_id, schedule_revision, scheduled_at,
                    target_kind, target_reference, created_at,
                    concurrency_json, retry_json, timeout_seconds,
                    state, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("request-b", *values),
            )
    finally:
        connection.close()


def test_t_sql_constraints_004_check_constraint_rejects_invalid_schedule_state(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    SqliteUnitOfWorkFactory(database)

    connection = _raw(database)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            connection.execute(
                """
                INSERT INTO schedules(
                    id, definition_json, state, revision,
                    persistence_version, next_run_time
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "broken",
                    "{}",
                    "not-a-state",
                    1,
                    0,
                    None,
                ),
            )
    finally:
        connection.close()


def test_t_sql_constraints_005_active_schedule_requires_next_run_time_in_database(
    tmp_path,
) -> None:
    database = tmp_path / "scheduler.db"
    SqliteUnitOfWorkFactory(database)

    connection = _raw(database)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            connection.execute(
                """
                INSERT INTO schedules(
                    id, definition_json, state, revision,
                    persistence_version, next_run_time
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "broken-active",
                    "{}",
                    "active",
                    1,
                    0,
                    None,
                ),
            )
    finally:
        connection.close()


def test_t_sql_constraints_006_foreign_keys_are_enabled_on_factory_connections(
    tmp_path,
) -> None:
    database = tmp_path / "scheduler.db"
    factory = SqliteUnitOfWorkFactory(database)

    with factory() as uow:
        connection = uow._connection  # type: ignore[attr-defined]
        row = connection.execute("PRAGMA foreign_keys").fetchone()

        assert row is not None
        assert int(row[0]) == 1


def test_t_sql_constraints_007_v1_database_migrates_to_current_schema(tmp_path) -> None:
    database = tmp_path / "scheduler.db"
    _create_v1_database(database)

    factory = SqliteUnitOfWorkFactory(database)

    with factory() as uow:
        loaded = uow.schedules.get(ScheduleId("legacy-schedule"))
        assert loaded is not None

    connection = _raw(database)
    try:
        version = connection.execute("SELECT version FROM pyschedulekit_schema").fetchone()
        assert version is not None
        assert int(version[0]) == 7

        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            connection.execute(
                """
                INSERT INTO schedules(
                    id, definition_json, state, revision,
                    persistence_version, next_run_time
                ) VALUES ('invalid', '{}', 'active', 1, 0, NULL)
                """
            )
    finally:
        connection.close()


def _create_v1_database(database) -> None:
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            """
            CREATE TABLE pyschedulekit_schema (
                version INTEGER NOT NULL
            );
            INSERT INTO pyschedulekit_schema(version) VALUES (1);

            CREATE TABLE schedules (
                id TEXT PRIMARY KEY,
                definition_json TEXT NOT NULL,
                state TEXT NOT NULL,
                revision INTEGER NOT NULL,
                persistence_version INTEGER NOT NULL,
                next_run_time TEXT
            );

            CREATE TABLE execution_requests (
                id TEXT PRIMARY KEY,
                schedule_id TEXT NOT NULL,
                schedule_revision INTEGER NOT NULL,
                scheduled_at TEXT NOT NULL,
                target_kind TEXT NOT NULL,
                target_reference TEXT NOT NULL,
                created_at TEXT NOT NULL,
                concurrency_json TEXT NOT NULL,
                retry_json TEXT NOT NULL,
                timeout_seconds REAL,
                state TEXT NOT NULL,
                version INTEGER NOT NULL
            );

            CREATE TABLE executions (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                target_kind TEXT NOT NULL,
                target_reference TEXT NOT NULL,
                created_at TEXT NOT NULL,
                policy_json TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                state TEXT NOT NULL,
                version INTEGER NOT NULL,
                attempt_count INTEGER NOT NULL,
                active_attempt_number INTEGER,
                next_attempt_at TEXT,
                cancellation_requested_at TEXT,
                result_json TEXT
            );

            CREATE TABLE attempts (
                id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                number INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                state TEXT NOT NULL,
                result_json TEXT,
                version INTEGER NOT NULL
            );
            """
        )

        legacy = _schedule("legacy-schedule")

        connection.execute(
            """
            INSERT INTO schedules(
                id, definition_json, state, revision,
                persistence_version, next_run_time
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                legacy.id.value,
                encode_schedule_definition(legacy.definition),
                legacy.state.value,
                legacy.revision.value,
                legacy.persistence_version.value,
                legacy.next_run_time.value.isoformat()
                if legacy.next_run_time is not None
                else None,
            ),
        )
        connection.commit()
    finally:
        connection.close()
