"""SQLite schema bootstrap for durable scheduler state."""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pyschedulekit_schema (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS schedules (
    id TEXT PRIMARY KEY,
    definition_json TEXT NOT NULL,
    state TEXT NOT NULL,
    revision INTEGER NOT NULL,
    persistence_version INTEGER NOT NULL,
    next_run_time TEXT
);

CREATE INDEX IF NOT EXISTS ix_schedules_due
    ON schedules(state, next_run_time, id);

CREATE TABLE IF NOT EXISTS execution_requests (
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

CREATE INDEX IF NOT EXISTS ix_execution_requests_occurrence
    ON execution_requests(schedule_id, schedule_revision, scheduled_at);

CREATE INDEX IF NOT EXISTS ix_execution_requests_admission
    ON execution_requests(state, scheduled_at, created_at, id);

CREATE TABLE IF NOT EXISTS executions (
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

CREATE INDEX IF NOT EXISTS ix_executions_request
    ON executions(request_id);

CREATE INDEX IF NOT EXISTS ix_executions_runnable
    ON executions(state, next_attempt_at, created_at, id);

CREATE TABLE IF NOT EXISTS attempts (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    number INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    state TEXT NOT NULL,
    result_json TEXT,
    version INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_attempts_execution_number
    ON attempts(execution_id, number);
"""


def initialize_sqlite_schema(connection: sqlite3.Connection) -> None:
    """Create the LOT-21 schema and verify its version."""

    connection.executescript(_SCHEMA_SQL)
    row = connection.execute("SELECT version FROM pyschedulekit_schema LIMIT 1").fetchone()
    if row is None:
        connection.execute(
            "INSERT INTO pyschedulekit_schema(version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        connection.commit()
        return

    if int(row[0]) != SCHEMA_VERSION:
        raise RuntimeError(f"Unsupported PyScheduleKit SQLite schema version: {row[0]!r}.")
