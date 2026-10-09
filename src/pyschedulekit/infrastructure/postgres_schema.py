"""PostgreSQL schema bootstrap for the current PyScheduleKit persistence model."""

from __future__ import annotations

from psycopg import Connection

SCHEMA_VERSION = 1

# Stable project-specific transaction advisory lock. It serializes first-time schema
# bootstrap without keeping any session-level lock after commit/rollback.
_SCHEMA_BOOTSTRAP_LOCK = 0x5059534348444B54

_METADATA_SQL = """
CREATE TABLE IF NOT EXISTS pyschedulekit_schema (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK(singleton),
    version INTEGER NOT NULL CHECK(version >= 1)
)
"""

_SCHEMA_SQL = (
    """
    CREATE TABLE IF NOT EXISTS schedules (
        id TEXT PRIMARY KEY CHECK(length(btrim(id)) > 0),
        definition_json TEXT NOT NULL,
        state TEXT NOT NULL
            CHECK(state IN ('active', 'paused', 'cancelled', 'completed')),
        revision INTEGER NOT NULL CHECK(revision >= 1),
        persistence_version INTEGER NOT NULL CHECK(persistence_version >= 0),
        next_run_time TIMESTAMPTZ,
        CHECK(
            (state = 'active' AND next_run_time IS NOT NULL)
            OR
            (state <> 'active' AND next_run_time IS NULL)
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS execution_requests (
        id TEXT PRIMARY KEY CHECK(length(btrim(id)) > 0),
        schedule_id TEXT NOT NULL,
        schedule_revision INTEGER NOT NULL CHECK(schedule_revision >= 1),
        scheduled_at TIMESTAMPTZ NOT NULL,
        target_kind TEXT NOT NULL CHECK(length(btrim(target_kind)) > 0),
        target_reference TEXT NOT NULL CHECK(length(btrim(target_reference)) > 0),
        created_at TIMESTAMPTZ NOT NULL,
        concurrency_json TEXT NOT NULL,
        retry_json TEXT NOT NULL,
        timeout_seconds DOUBLE PRECISION
            CHECK(timeout_seconds IS NULL OR timeout_seconds > 0),
        state TEXT NOT NULL
            CHECK(state IN (
                'pending', 'waiting_admission', 'dispatched', 'dropped', 'cancelled'
            )),
        version INTEGER NOT NULL CHECK(version >= 0),
        FOREIGN KEY(schedule_id) REFERENCES schedules(id) ON DELETE RESTRICT,
        UNIQUE(schedule_id, schedule_revision, scheduled_at)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS executions (
        id TEXT PRIMARY KEY CHECK(length(btrim(id)) > 0),
        request_id TEXT NOT NULL UNIQUE,
        target_kind TEXT NOT NULL CHECK(length(btrim(target_kind)) > 0),
        target_reference TEXT NOT NULL CHECK(length(btrim(target_reference)) > 0),
        created_at TIMESTAMPTZ NOT NULL,
        policy_json TEXT NOT NULL,
        idempotency_key TEXT NOT NULL UNIQUE CHECK(length(btrim(idempotency_key)) > 0),
        state TEXT NOT NULL
            CHECK(state IN (
                'queued', 'running', 'retry_wait',
                'success', 'failed', 'cancelled', 'timed_out'
            )),
        version INTEGER NOT NULL CHECK(version >= 0),
        attempt_count INTEGER NOT NULL CHECK(attempt_count >= 0),
        active_attempt_number INTEGER
            CHECK(active_attempt_number IS NULL OR active_attempt_number >= 1),
        next_attempt_at TIMESTAMPTZ,
        cancellation_requested_at TIMESTAMPTZ,
        result_json TEXT,
        completed_at TIMESTAMPTZ,
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
                AND completed_at IS NOT NULL
            )
            OR
            (
                state IN ('queued', 'running', 'retry_wait')
                AND result_json IS NULL
                AND completed_at IS NULL
            )
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS attempts (
        id TEXT PRIMARY KEY CHECK(length(btrim(id)) > 0),
        execution_id TEXT NOT NULL,
        number INTEGER NOT NULL CHECK(number >= 1),
        started_at TIMESTAMPTZ NOT NULL,
        state TEXT NOT NULL
            CHECK(state IN ('running', 'success', 'failed', 'timed_out', 'cancelled')),
        result_json TEXT,
        version INTEGER NOT NULL CHECK(version >= 0),
        FOREIGN KEY(execution_id) REFERENCES executions(id) ON DELETE RESTRICT,
        UNIQUE(execution_id, number),
        CHECK(
            (state = 'running' AND result_json IS NULL)
            OR
            (state <> 'running' AND result_json IS NOT NULL)
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS outbox_messages (
        id TEXT PRIMARY KEY CHECK(length(btrim(id)) > 0),
        event_type TEXT NOT NULL CHECK(length(btrim(event_type)) > 0),
        aggregate_type TEXT NOT NULL CHECK(length(btrim(aggregate_type)) > 0),
        aggregate_id TEXT NOT NULL CHECK(length(btrim(aggregate_id)) > 0),
        payload_json TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        sequence INTEGER NOT NULL CHECK(sequence >= 0),
        state TEXT NOT NULL CHECK(state IN ('pending', 'published')),
        published_at TIMESTAMPTZ,
        publish_attempts INTEGER NOT NULL CHECK(publish_attempts >= 0),
        last_error TEXT,
        version INTEGER NOT NULL CHECK(version >= 0),
        CHECK(
            (state = 'pending' AND published_at IS NULL)
            OR
            (state = 'published' AND published_at IS NOT NULL)
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS execution_claims (
        execution_id TEXT PRIMARY KEY,
        worker_id TEXT NOT NULL CHECK(length(btrim(worker_id)) > 0),
        token TEXT NOT NULL UNIQUE CHECK(length(btrim(token)) > 0),
        claimed_at TIMESTAMPTZ NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        generation INTEGER NOT NULL CHECK(generation >= 1),
        state TEXT NOT NULL CHECK(state IN ('active', 'released')),
        released_at TIMESTAMPTZ,
        version INTEGER NOT NULL CHECK(version >= 0),
        FOREIGN KEY(execution_id) REFERENCES executions(id) ON DELETE CASCADE,
        CHECK(expires_at > claimed_at),
        CHECK(
            (state = 'active' AND released_at IS NULL)
            OR
            (state = 'released' AND released_at IS NOT NULL)
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS schedule_admission_locks (
        schedule_id TEXT PRIMARY KEY,
        worker_id TEXT NOT NULL CHECK(length(btrim(worker_id)) > 0),
        token TEXT NOT NULL UNIQUE CHECK(length(btrim(token)) > 0),
        acquired_at TIMESTAMPTZ NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        generation INTEGER NOT NULL CHECK(generation >= 1),
        state TEXT NOT NULL CHECK(state IN ('active', 'released')),
        released_at TIMESTAMPTZ,
        version INTEGER NOT NULL CHECK(version >= 0),
        FOREIGN KEY(schedule_id) REFERENCES schedules(id) ON DELETE CASCADE,
        CHECK(expires_at > acquired_at),
        CHECK(
            (state = 'active' AND released_at IS NULL)
            OR
            (state = 'released' AND released_at IS NOT NULL)
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS schedule_materialization_leases (
        schedule_id TEXT PRIMARY KEY,
        worker_id TEXT NOT NULL CHECK(length(btrim(worker_id)) > 0),
        token TEXT NOT NULL UNIQUE CHECK(length(btrim(token)) > 0),
        acquired_at TIMESTAMPTZ NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        generation INTEGER NOT NULL CHECK(generation >= 1),
        state TEXT NOT NULL CHECK(state IN ('active', 'released')),
        released_at TIMESTAMPTZ,
        version INTEGER NOT NULL CHECK(version >= 0),
        FOREIGN KEY(schedule_id) REFERENCES schedules(id) ON DELETE CASCADE,
        CHECK(expires_at > acquired_at),
        CHECK(
            (state = 'active' AND released_at IS NULL)
            OR
            (state = 'released' AND released_at IS NOT NULL)
        )
    )
    """,
)

_INDEX_SQL = (
    """
    CREATE INDEX IF NOT EXISTS ix_schedules_due
        ON schedules(state, next_run_time, id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_execution_requests_admission
        ON execution_requests(state, scheduled_at, created_at, id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_executions_runnable
        ON executions(state, next_attempt_at, created_at, id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_attempts_execution_number
        ON attempts(execution_id, number)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_outbox_pending
        ON outbox_messages(
            state, created_at, aggregate_type, aggregate_id, sequence, id
        )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_execution_claims_active
        ON execution_claims(state, expires_at, execution_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_schedule_admission_locks_active
        ON schedule_admission_locks(state, expires_at, schedule_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_schedule_materialization_leases_active
        ON schedule_materialization_leases(state, expires_at, schedule_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_executions_retention
        ON executions(state, completed_at, id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_execution_requests_retention
        ON execution_requests(state, created_at, id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_outbox_published
        ON outbox_messages(state, published_at, id)
    """,
)

_REQUIRED_TABLES = frozenset(
    {
        "pyschedulekit_schema",
        "schedules",
        "execution_requests",
        "executions",
        "attempts",
        "outbox_messages",
        "execution_claims",
        "schedule_admission_locks",
        "schedule_materialization_leases",
    }
)

_TEMPORAL_COLUMNS = frozenset(
    {
        ("schedules", "next_run_time"),
        ("execution_requests", "scheduled_at"),
        ("execution_requests", "created_at"),
        ("executions", "created_at"),
        ("executions", "next_attempt_at"),
        ("executions", "cancellation_requested_at"),
        ("executions", "completed_at"),
        ("attempts", "started_at"),
        ("outbox_messages", "created_at"),
        ("outbox_messages", "published_at"),
        ("execution_claims", "claimed_at"),
        ("execution_claims", "expires_at"),
        ("execution_claims", "released_at"),
        ("schedule_admission_locks", "acquired_at"),
        ("schedule_admission_locks", "expires_at"),
        ("schedule_admission_locks", "released_at"),
        ("schedule_materialization_leases", "acquired_at"),
        ("schedule_materialization_leases", "expires_at"),
        ("schedule_materialization_leases", "released_at"),
    }
)


def initialize_postgres_schema(connection: Connection[tuple[object, ...]]) -> None:
    """Create and verify the initial PostgreSQL schema atomically."""

    with connection.transaction():
        connection.execute(
            "SELECT pg_advisory_xact_lock(%s)",
            (_SCHEMA_BOOTSTRAP_LOCK,),
        )
        connection.execute(_METADATA_SQL)

        rows = connection.execute(
            "SELECT version FROM pyschedulekit_schema FOR UPDATE"
        ).fetchall()
        if len(rows) > 1:
            raise RuntimeError("PyScheduleKit PostgreSQL schema has multiple version rows.")

        if rows:
            version = int(rows[0][0])
            if version != SCHEMA_VERSION:
                raise RuntimeError(
                    "Unsupported PyScheduleKit PostgreSQL schema version: "
                    f"{version!r}."
                )
        else:
            for statement in _SCHEMA_SQL:
                connection.execute(statement)
            for statement in _INDEX_SQL:
                connection.execute(statement)
            connection.execute(
                """
                INSERT INTO pyschedulekit_schema(singleton, version)
                VALUES (TRUE, %s)
                """,
                (SCHEMA_VERSION,),
            )

        _verify_postgres_schema(connection)


def _verify_postgres_schema(connection: Connection[tuple[object, ...]]) -> None:
    tables = {
        str(row[0])
        for row in connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = current_schema()
            """
        ).fetchall()
    }
    missing_tables = _REQUIRED_TABLES - tables
    if missing_tables:
        raise RuntimeError(
            "PyScheduleKit PostgreSQL schema is incomplete; missing tables: "
            f"{sorted(missing_tables)!r}."
        )

    temporal_columns = {
        (str(row[0]), str(row[1]))
        for row in connection.execute(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND data_type = 'timestamp with time zone'
            """
        ).fetchall()
    }
    missing_temporal_columns = _TEMPORAL_COLUMNS - temporal_columns
    if missing_temporal_columns:
        raise RuntimeError(
            "PyScheduleKit PostgreSQL temporal schema is incomplete: "
            f"{sorted(missing_temporal_columns)!r}."
        )

    row = connection.execute(
        "SELECT version FROM pyschedulekit_schema"
    ).fetchone()
    if row is None or int(row[0]) != SCHEMA_VERSION:
        raise RuntimeError("PyScheduleKit PostgreSQL schema version verification failed.")
