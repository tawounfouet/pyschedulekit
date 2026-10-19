"""V1-02.C physical SQLite forward-migration qualification."""

from __future__ import annotations

import hashlib
import json
import lzma
import sqlite3
from pathlib import Path

import pytest

from pyschedulekit.domain.execution import ExecutionId
from pyschedulekit.domain.execution_request import RequestId
from pyschedulekit.domain.schedule import ScheduleId
from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory
from pyschedulekit.infrastructure.sqlite_schema import SCHEMA_VERSION

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "persistence" / "v1" / "sqlite"
EXPECTED_FIXTURES = {
    1: (
        "sqlite_schema_v1.db.xz",
        1344,
        "d3dce29ca2af8ce20526fbad3fed81b625dd558826fc21b4023f373d220f245d",
        40960,
        "6883235eb603e79cc393070f604f321811848544e7a9c0f1ef3642f781533c79",
    ),
    2: (
        "sqlite_schema_v2.db.xz",
        2104,
        "34d2d9dc61a08e7316d9e73fb6b0246f0d7eaa100c6ad8d3bf0d415781f0864b",
        81920,
        "e8c65dff44bae7dd6c41763cfa250f154f0fd5c1bd94bb164e1824ca44667f9e",
    ),
    3: (
        "sqlite_schema_v3.db.xz",
        2408,
        "0ba04dbc828aabdf9063653456547ad67e43c3975dbb95a86f96b0765d5b3efe",
        94208,
        "89a7e510a08ca54ac6304c129ad9c5d90e3b9907a8dfb28e7d1c59bb69ac5f8d",
    ),
    4: (
        "sqlite_schema_v4.db.xz",
        2664,
        "f6b6d974be342e17a96a0626cae5fd12af4a1ce239ca36666170964a39cc2fc4",
        110592,
        "98298c155f13c4204263ae97550d9e58d6dedd61bf14ea230f78f60507ee6db4",
    ),
    5: (
        "sqlite_schema_v5.db.xz",
        2840,
        "0a437c050624de8bfa5b9061020ef468bb510df0ab04733b5bf906ba72881627",
        126976,
        "f440260e934696457f45ba532dc2042458c1b18cc2719e251593a5563e6525e2",
    ),
    6: (
        "sqlite_schema_v6.db.xz",
        2872,
        "b73f4236498c0e78dcfeda5cd36aacd44f0b6915b8fe800972a2b208b1c33654",
        126976,
        "83aaa42b892e846c422242c12da39a824731256234f4c625bf8204ba4b06586d",
    ),
    7: (
        "sqlite_schema_v7.db.xz",
        3108,
        "50bde5adc60c63a657e86c5475a452d5a8aae37004eb96ddca320c16967b0f4e",
        147456,
        "b9570c1346b63ea3aa4ce342f08a36a489f09009044a03431b407a7972c97747",
    ),
}

CORE_TABLES = {
    "attempts",
    "execution_requests",
    "executions",
    "pyschedulekit_schema",
    "schedules",
}
CURRENT_TABLES = CORE_TABLES | {
    "execution_claims",
    "outbox_messages",
    "schedule_admission_locks",
    "schedule_materialization_leases",
}
CURRENT_INDEXES = {
    "ix_attempts_execution_number",
    "ix_execution_claims_active",
    "ix_execution_requests_admission",
    "ix_execution_requests_retention",
    "ix_executions_retention",
    "ix_executions_runnable",
    "ix_outbox_pending",
    "ix_outbox_published",
    "ix_schedule_admission_locks_active",
    "ix_schedule_materialization_leases_active",
    "ix_schedules_due",
}


def _fixture_payload(version: int) -> bytes:
    name, compressed_size, compressed_hash, raw_size, raw_hash = EXPECTED_FIXTURES[version]
    compressed = (FIXTURE_ROOT / name).read_bytes()

    assert len(compressed) == compressed_size
    assert hashlib.sha256(compressed).hexdigest() == compressed_hash

    raw = lzma.decompress(compressed)
    assert len(raw) == raw_size
    assert hashlib.sha256(raw).hexdigest() == raw_hash
    return raw


def _copy_fixture(version: int, tmp_path: Path) -> Path:
    database = tmp_path / f"sqlite-v{version}.db"
    database.write_bytes(_fixture_payload(version))
    return database


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _indexes(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


@pytest.mark.parametrize("version", range(1, 8))
def test_v1_02c_physical_fixture_identity_and_historical_shape(version: int, tmp_path: Path) -> None:
    database = _copy_fixture(version, tmp_path)

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("SELECT version FROM pyschedulekit_schema").fetchone() == (
            version,
        )

        expected_tables = set(CORE_TABLES)
        if version >= 3:
            expected_tables.add("outbox_messages")
        if version >= 4:
            expected_tables.add("execution_claims")
        if version >= 5:
            expected_tables.add("schedule_admission_locks")
        if version >= 7:
            expected_tables.add("schedule_materialization_leases")
        assert _tables(connection) == expected_tables

        if version >= 4:
            assert ("generation" in _columns(connection, "execution_claims")) is (version >= 6)
        if version >= 5:
            assert ("generation" in _columns(connection, "schedule_admission_locks")) is (
                version >= 6
            )
        assert "completed_at" not in _columns(connection, "executions")


@pytest.mark.parametrize("version", range(1, 8))
def test_v1_02c_every_supported_sqlite_schema_migrates_to_v8(
    version: int,
    tmp_path: Path,
) -> None:
    database = _copy_fixture(version, tmp_path)

    factory = SqliteUnitOfWorkFactory(database)

    with factory() as uow:
        schedule = uow.schedules.get(ScheduleId("legacy-schedule"))
        request = uow.requests.get(RequestId("legacy-request"))
        execution = uow.executions.get(ExecutionId("legacy-execution"))
        attempts = uow.attempts.list_for_execution(ExecutionId("legacy-execution"))

        assert schedule is not None
        assert schedule.definition.target.reference == "jobs:interval"
        assert schedule.definition.calendar is None
        assert request is not None
        assert request.target.reference == "jobs:interval"
        assert execution is not None
        assert execution.state.value == "success"
        assert execution.result is not None
        assert execution.result.completed_at.value.isoformat() == "2026-01-01T10:05:00+00:00"
        assert len(attempts) == 1
        assert attempts[0].id.value == "legacy-attempt"
        assert attempts[0].state.value == "success"

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT version FROM pyschedulekit_schema").fetchone() == (
            SCHEMA_VERSION,
        )
        assert _tables(connection) == CURRENT_TABLES
        assert CURRENT_INDEXES <= _indexes(connection)

        assert connection.execute(
            "SELECT id, state, revision, persistence_version FROM schedules"
        ).fetchone() == ("legacy-schedule", "active", 1, 0)
        assert connection.execute(
            "SELECT id, schedule_id, state, version FROM execution_requests"
        ).fetchone() == ("legacy-request", "legacy-schedule", "dispatched", 1)
        assert connection.execute(
            "SELECT id, request_id, state, version, attempt_count, completed_at FROM executions"
        ).fetchone() == (
            "legacy-execution",
            "legacy-request",
            "success",
            2,
            1,
            "2026-01-01T10:05:00+00:00",
        )
        assert connection.execute(
            "SELECT id, execution_id, number, state, version FROM attempts"
        ).fetchone() == ("legacy-attempt", "legacy-execution", 1, "success", 1)

        outbox = connection.execute(
            "SELECT id, state, publish_attempts FROM outbox_messages WHERE id = 'legacy-outbox'"
        ).fetchone()
        assert outbox == (("legacy-outbox", "published", 1) if version >= 3 else None)

        claim = connection.execute(
            "SELECT execution_id, state, generation FROM execution_claims "
            "WHERE execution_id = 'legacy-execution'"
        ).fetchone()
        if version >= 4:
            assert claim == ("legacy-execution", "released", 3 if version >= 6 else 1)
        else:
            assert claim is None

        lock = connection.execute(
            "SELECT schedule_id, state, generation FROM schedule_admission_locks "
            "WHERE schedule_id = 'legacy-schedule'"
        ).fetchone()
        if version >= 5:
            assert lock == ("legacy-schedule", "released", 4 if version >= 6 else 1)
        else:
            assert lock is None

        lease = connection.execute(
            "SELECT schedule_id, state, generation FROM schedule_materialization_leases "
            "WHERE schedule_id = 'legacy-schedule'"
        ).fetchone()
        assert lease == (
            ("legacy-schedule", "released", 5) if version >= 7 else None
        )


def test_v1_02c_manifest_matches_executable_fixture_baseline() -> None:
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 1
    assert manifest["source_baseline"] == "3cd1787d8a3fb15bd790daad50d1432294b32f19"
    assert manifest["compression"] == "xz"
    assert manifest["policy"] == {
        "mutation": "append-only",
        "migration_target": 8,
        "fixture_kind": "physical-sqlite-database",
        "copy_before_migration": True,
    }

    actual = {
        int(item["version"]): (
            item["file"],
            int(item["compressed_size"]),
            item["compressed_sha256"],
            int(item["raw_size"]),
            item["raw_sha256"],
        )
        for item in manifest["fixtures"]
    }
    assert actual == EXPECTED_FIXTURES
