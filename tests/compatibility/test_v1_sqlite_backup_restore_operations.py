"""V1-02.F SQLite backup, restore and interrupted-migration qualification."""

from __future__ import annotations

import lzma
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleState,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure import sqlite_schema
from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory
from pyschedulekit.infrastructure.persistence_versions import SQLITE_RUNTIME_SCHEMA_VERSION

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "persistence" / "v1" / "sqlite"


def _instant(*, hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _schedule(schedule_id: str) -> Schedule:
    return Schedule.create(
        schedule_id=ScheduleId(schedule_id),
        definition=ScheduleDefinition(
            target=TargetRef.python(f"jobs:{schedule_id}"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(minute=10),
            ),
        ),
        reference=_instant(hour=9),
    )


def _backup_sqlite(source_path: Path, backup_path: Path) -> None:
    with sqlite3.connect(source_path) as source, sqlite3.connect(backup_path) as destination:
        source.backup(destination)


def _schema_version(database: Path) -> int:
    with sqlite3.connect(database) as connection:
        row = connection.execute("SELECT version FROM pyschedulekit_schema").fetchone()
    assert row is not None
    return int(row[0])


def _integrity(database: Path) -> str:
    with sqlite3.connect(database) as connection:
        row = connection.execute("PRAGMA integrity_check").fetchone()
    assert row is not None
    return str(row[0])


def _inflate_v7_fixture(destination: Path) -> None:
    compressed = (FIXTURE_ROOT / "sqlite_schema_v7.db.xz").read_bytes()
    destination.write_bytes(lzma.decompress(compressed))


def test_v1_02f_sqlite_online_backup_restores_committed_domain_state(tmp_path: Path) -> None:
    live = tmp_path / "live.db"
    backup = tmp_path / "live.backup.db"
    restored = tmp_path / "restored.db"
    schedule = _schedule("backup-restore")

    factory = SqliteUnitOfWorkFactory(live)
    with factory() as uow:
        uow.schedules.add(schedule)
        uow.commit()

    _backup_sqlite(live, backup)

    assert backup.is_file()
    assert backup.stat().st_size > 0
    assert _integrity(backup) == "ok"
    assert _schema_version(backup) == SQLITE_RUNTIME_SCHEMA_VERSION

    with factory() as uow:
        loaded = uow.schedules.get(schedule.id)
        assert loaded is not None
        loaded.pause()
        uow.schedules.save(loaded)
        uow.commit()

    shutil.copy2(backup, restored)
    restored_factory = SqliteUnitOfWorkFactory(restored)
    with restored_factory() as uow:
        recovered = uow.schedules.get(schedule.id)

    assert recovered is not None
    assert recovered.state is ScheduleState.ACTIVE
    assert recovered.next_run_time == _instant(minute=10)


def test_v1_02f_sqlite_preupgrade_backup_remains_known_good_after_live_migration(
    tmp_path: Path,
) -> None:
    live = tmp_path / "schema-v7-live.db"
    backup = tmp_path / "schema-v7-backup.db"
    restored = tmp_path / "schema-v7-restored.db"

    _inflate_v7_fixture(live)
    assert _schema_version(live) == 7
    assert _integrity(live) == "ok"

    _backup_sqlite(live, backup)
    assert _schema_version(backup) == 7
    assert _integrity(backup) == "ok"

    SqliteUnitOfWorkFactory(live)
    assert _schema_version(live) == SQLITE_RUNTIME_SCHEMA_VERSION
    assert _integrity(live) == "ok"

    shutil.copy2(backup, restored)
    assert _schema_version(restored) == 7
    assert _integrity(restored) == "ok"

    with sqlite3.connect(restored) as connection:
        schedules = connection.execute("SELECT COUNT(*) FROM schedules").fetchone()
        executions = connection.execute("SELECT COUNT(*) FROM executions").fetchone()
        columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(executions)").fetchall()
        }

    assert schedules is not None and int(schedules[0]) > 0
    assert executions is not None and int(executions[0]) > 0
    assert "completed_at" not in columns


def test_v1_02f_sqlite_interrupted_v7_to_v8_migration_rolls_back_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = tmp_path / "interrupted-v7.db"
    _inflate_v7_fixture(live)

    assert _schema_version(live) == 7
    assert _integrity(live) == "ok"

    def fail_after_first_ddl(connection: sqlite3.Connection) -> None:
        connection.execute("ALTER TABLE executions ADD COLUMN completed_at TEXT")
        raise RuntimeError("forced migration interruption")

    monkeypatch.setattr(sqlite_schema, "_add_retention_v8_columns", fail_after_first_ddl)

    with pytest.raises(RuntimeError, match="forced migration interruption"):
        SqliteUnitOfWorkFactory(live)

    assert _schema_version(live) == 7
    assert _integrity(live) == "ok"

    with sqlite3.connect(live) as connection:
        columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(executions)").fetchall()
        }
        schema_rows = connection.execute(
            "SELECT singleton, version FROM pyschedulekit_schema"
        ).fetchall()

    assert "completed_at" not in columns
    assert schema_rows == [(1, 7)]
