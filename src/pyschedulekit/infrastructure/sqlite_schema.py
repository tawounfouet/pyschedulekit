"""SQLite schema bootstrap and migrations for durable scheduler state."""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 3

_TABLES_V2_SQL = """
CREATE TABLE schedules (
    id TEXT PRIMARY KEY
        CHECK(length(trim(id)) > 0),
    definition_json TEXT NOT NULL,
    state TEXT NOT NULL
        CHECK(state IN ('active', 'paused', 'cancelled', 'completed')),
    revision INTEGER NOT NULL
        CHECK(revision >= 1),
    persistence_version INTEGER NOT NULL
        CHECK(persistence_version >= 0),
    next_run_time TEXT,
    CHECK(
        (state = 'active' AND next_run_time IS NOT NULL)
        OR
        (state <> 'active' AND next_run_time IS NULL)
    )
);

CREATE TABLE execution_requests (
    id TEXT PRIMARY KEY
        CHECK(length(trim(id)) > 0),
    schedule_id TEXT NOT NULL,
    schedule_revision INTEGER NOT NULL
        CHECK(schedule_revision >= 1),
    scheduled_at TEXT NOT NULL,
    target_kind TEXT NOT NULL
        CHECK(length(trim(target_kind)) > 0),
    target_reference TEXT NOT NULL
        CHECK(length(trim(target_reference)) > 0),
    created_at TEXT NOT NULL,
    concurrency_json TEXT NOT NULL,
    retry_json TEXT NOT NULL,
    timeout_seconds REAL
        CHECK(timeout_seconds IS NULL OR timeout_seconds > 0),
    state TEXT NOT NULL
        CHECK(state IN ('pending', 'waiting_admission', 'dispatched', 'dropped', 'cancelled')),
    version INTEGER NOT NULL
        CHECK(version >= 0),
    FOREIGN KEY(schedule_id) REFERENCES schedules(id) ON DELETE RESTRICT,
    UNIQUE(schedule_id, schedule_revision, scheduled_at)
);

CREATE TABLE executions (
    id TEXT PRIMARY KEY
        CHECK(length(trim(id)) > 0),
    request_id TEXT NOT NULL UNIQUE,
    target_kind TEXT NOT NULL
        CHECK(length(trim(target_kind)) > 0),
    target_reference TEXT NOT NULL
        CHECK(length(trim(target_reference)) > 0),
    created_at TEXT NOT NULL,
    policy_json TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE
        CHECK(length(trim(idempotency_key)) > 0),
    state TEXT NOT NULL
        CHECK(state IN (
            'queued', 'running', 'retry_wait',
            'success', 'failed', 'cancelled', 'timed_out'
        )),
    version INTEGER NOT NULL
        CHECK(version >= 0),
    attempt_count INTEGER NOT NULL
        CHECK(attempt_count >= 0),
    active_attempt_number INTEGER
        CHECK(active_attempt_number IS NULL OR active_attempt_number >= 1),
    next_attempt_at TEXT,
    cancellation_requested_at TEXT,
    result_json TEXT,
    FOREIGN KEY(request_id) REFERENCES execution_requests(id) ON DELETE RESTRICT,
    CHECK(
        (state = 'running' AND active_attempt_number IS NOT NULL)
        OR
        (state <> 'running' AND active_attempt_number IS NULL)
    ),
    CHECK(
        (state = 'retry_wait' AND next_attempt_at IS NOT NULL)
        OR
        (state <> 'retry_wait' AND next_attempt_at IS NULL)
    ),
    CHECK(
        (
            state IN ('success', 'failed', 'cancelled', 'timed_out')
            AND result_json IS NOT NULL
        )
        OR
        (
            state IN ('queued', 'running', 'retry_wait')
            AND result_json IS NULL
        )
    )
);

CREATE TABLE attempts (
    id TEXT PRIMARY KEY
        CHECK(length(trim(id)) > 0),
    execution_id TEXT NOT NULL,
    number INTEGER NOT NULL
        CHECK(number >= 1),
    started_at TEXT NOT NULL,
    state TEXT NOT NULL
        CHECK(state IN ('running', 'success', 'failed', 'timed_out', 'cancelled')),
    result_json TEXT,
    version INTEGER NOT NULL
        CHECK(version >= 0),
    FOREIGN KEY(execution_id) REFERENCES executions(id) ON DELETE RESTRICT,
    UNIQUE(execution_id, number),
    CHECK(
        (state = 'running' AND result_json IS NULL)
        OR
        (state <> 'running' AND result_json IS NOT NULL)
    )
);
"""

_OUTBOX_V3_SQL = """
CREATE TABLE outbox_messages (
    id TEXT PRIMARY KEY
        CHECK(length(trim(id)) > 0),
    event_type TEXT NOT NULL
        CHECK(length(trim(event_type)) > 0),
    aggregate_type TEXT NOT NULL
        CHECK(length(trim(aggregate_type)) > 0),
    aggregate_id TEXT NOT NULL
        CHECK(length(trim(aggregate_id)) > 0),
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    state TEXT NOT NULL
        CHECK(state IN ('pending', 'published')),
    published_at TEXT,
    publish_attempts INTEGER NOT NULL
        CHECK(publish_attempts >= 0),
    last_error TEXT,
    version INTEGER NOT NULL
        CHECK(version >= 0),
    CHECK(
        (state = 'pending' AND published_at IS NULL)
        OR
        (state = 'published' AND published_at IS NOT NULL)
    )
);
"""

_INDEXES_V2_SQL = """
CREATE INDEX ix_schedules_due
    ON schedules(state, next_run_time, id);

CREATE INDEX ix_execution_requests_admission
    ON execution_requests(state, scheduled_at, created_at, id);

CREATE INDEX ix_executions_runnable
    ON executions(state, next_attempt_at, created_at, id);

CREATE INDEX ix_attempts_execution_number
    ON attempts(execution_id, number);
"""

_INDEXES_V3_SQL = """
CREATE INDEX ix_outbox_pending
    ON outbox_messages(state, created_at, id);
"""


def initialize_sqlite_schema(connection: sqlite3.Connection) -> None:
    """Create or migrate the durable SQLite schema to the current version."""

    connection.execute("PRAGMA foreign_keys = ON")

    if not _schema_metadata_exists(connection):
        _create_v3_schema(connection)
        return

    row = connection.execute("SELECT version FROM pyschedulekit_schema LIMIT 1").fetchone()
    if row is None:
        raise RuntimeError("PyScheduleKit schema metadata exists without a version row.")

    version = int(row[0])
    if version == SCHEMA_VERSION:
        _verify_v3_schema(connection)
        return
    if version == 1:
        _migrate_v1_to_v2(connection)
        version = 2
    if version == 2:
        _migrate_v2_to_v3(connection)
        return

    raise RuntimeError(f"Unsupported PyScheduleKit SQLite schema version: {version!r}.")


def _schema_metadata_exists(connection: sqlite3.Connection) -> bool:
    return (
        connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'pyschedulekit_schema'
            """
        ).fetchone()
        is not None
    )


def _create_v3_schema(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            "CREATE TABLE pyschedulekit_schema (version INTEGER NOT NULL CHECK(version >= 1))"
        )
        _execute_sql_batch(connection, _TABLES_V2_SQL)
        _execute_sql_batch(connection, _OUTBOX_V3_SQL)
        _execute_sql_batch(connection, _INDEXES_V2_SQL)
        _execute_sql_batch(connection, _INDEXES_V3_SQL)
        connection.execute(
            "INSERT INTO pyschedulekit_schema(version) VALUES (?)",
            (2,),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    _verify_v3_schema(connection)


def _migrate_v1_to_v2(connection: sqlite3.Connection) -> None:
    connection.commit()
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("BEGIN IMMEDIATE")
    try:
        for index_name in (
            "ix_schedules_due",
            "ix_execution_requests_occurrence",
            "ix_execution_requests_admission",
            "ix_executions_request",
            "ix_executions_runnable",
            "ix_attempts_execution_number",
        ):
            connection.execute(f"DROP INDEX IF EXISTS {index_name}")

        connection.execute("ALTER TABLE attempts RENAME TO attempts_v1")
        connection.execute("ALTER TABLE executions RENAME TO executions_v1")
        connection.execute("ALTER TABLE execution_requests RENAME TO execution_requests_v1")
        connection.execute("ALTER TABLE schedules RENAME TO schedules_v1")

        _execute_sql_batch(connection, _TABLES_V2_SQL)

        connection.execute(
            """
            INSERT INTO schedules
            SELECT id, definition_json, state, revision,
                   persistence_version, next_run_time
            FROM schedules_v1
            """
        )
        connection.execute(
            """
            INSERT INTO execution_requests
            SELECT id, schedule_id, schedule_revision, scheduled_at,
                   target_kind, target_reference, created_at,
                   concurrency_json, retry_json, timeout_seconds,
                   state, version
            FROM execution_requests_v1
            """
        )
        connection.execute(
            """
            INSERT INTO executions
            SELECT id, request_id, target_kind, target_reference, created_at,
                   policy_json, idempotency_key, state, version, attempt_count,
                   active_attempt_number, next_attempt_at,
                   cancellation_requested_at, result_json
            FROM executions_v1
            """
        )
        connection.execute(
            """
            INSERT INTO attempts
            SELECT id, execution_id, number, started_at,
                   state, result_json, version
            FROM attempts_v1
            """
        )

        connection.execute("DROP TABLE attempts_v1")
        connection.execute("DROP TABLE executions_v1")
        connection.execute("DROP TABLE execution_requests_v1")
        connection.execute("DROP TABLE schedules_v1")

        _execute_sql_batch(connection, _INDEXES_V2_SQL)

        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(
                f"PyScheduleKit SQLite migration produced foreign-key violations: {violations!r}."
            )

        connection.execute(
            "UPDATE pyschedulekit_schema SET version = ?",
            (SCHEMA_VERSION,),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")

    _verify_v2_schema(connection)


def _migrate_v2_to_v3(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        _execute_sql_batch(connection, _OUTBOX_V3_SQL)
        _execute_sql_batch(connection, _INDEXES_V3_SQL)
        connection.execute(
            "UPDATE pyschedulekit_schema SET version = ?",
            (SCHEMA_VERSION,),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    _verify_v3_schema(connection)


def _verify_v2_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(f"PyScheduleKit SQLite foreign-key validation failed: {violations!r}.")


def _verify_v3_schema(connection: sqlite3.Connection) -> None:
    _verify_v2_schema(connection)
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'outbox_messages'
        """
    ).fetchone()
    if row is None:
        raise RuntimeError("PyScheduleKit SQLite outbox table is missing from schema v3.")


def _execute_sql_batch(connection: sqlite3.Connection, sql: str) -> None:
    """Execute a static semicolon-delimited SQL batch without implicit commits."""

    for statement in sql.split(";"):
        normalized = statement.strip()
        if normalized:
            connection.execute(normalized)
