"""V1-02.A executable persistence-version floor and evolution policy."""

from pyschedulekit.infrastructure.calendar import SqliteCalendarProvider
from pyschedulekit.infrastructure.calendar_codec import (
    _CALENDAR_CODEC_VERSION,
    _CALENDAR_COLLECTION_CODEC_VERSION,
)
from pyschedulekit.infrastructure.persistence_versions import (
    CALENDAR_COLLECTION_CODEC_VERSION,
    CALENDAR_VALUE_CODEC_VERSION,
    POSTGRES_RUNTIME_SCHEMA_VERSION,
    SCHEDULE_DEFINITION_CODEC_VERSION,
    SQL_VALUE_CODEC_VERSION,
    SQLITE_CALENDAR_SCHEMA_VERSION,
    SQLITE_RUNTIME_SCHEMA_VERSION,
    TRIGGER_CODEC_VERSION,
    V1_PERSISTENCE_COMPATIBILITY_RULES,
    V1_PERSISTENCE_CURRENT_WRITE_VERSIONS,
    V1_PERSISTENCE_VERSION_FLOORS,
)
from pyschedulekit.infrastructure.postgres_schema import SCHEMA_VERSION as POSTGRES_SCHEMA_VERSION
from pyschedulekit.infrastructure.sql_codec import (
    _CODEC_VERSION,
    _SCHEDULE_DEFINITION_CODEC_VERSION,
    _TRIGGER_CODEC_VERSION,
)
from pyschedulekit.infrastructure.sqlite_schema import SCHEMA_VERSION as SQLITE_SCHEMA_VERSION

EXPECTED_FLOORS = {
    "calendar-collection-codec": 1,
    "calendar-value-codec": 1,
    "postgres-runtime-schema": 1,
    "schedule-definition-codec": 1,
    "sql-value-codec": 1,
    "sqlite-calendar-schema": 1,
    "sqlite-runtime-schema": 1,
    "trigger-envelope-codec": 1,
}

EXPECTED_CURRENT_WRITERS = {
    "calendar-collection-codec": 1,
    "calendar-value-codec": 1,
    "postgres-runtime-schema": 1,
    "schedule-definition-codec": 3,
    "sql-value-codec": 1,
    "sqlite-calendar-schema": 1,
    "sqlite-runtime-schema": 8,
    "trigger-envelope-codec": 1,
}

EXPECTED_RULES = {
    "cross-adapter-data-migration": "unsupported",
    "downgrade-readability": "not-guaranteed",
    "future-version-policy": "fail-closed",
    "mixed-version-workers": "explicit-overlap-qualification-required",
    "read-floor-lifetime": "frozen-through-1.x",
    "schema-upgrade-backup": "required-before-format-changing-upgrade",
    "writer-evolution": "forward-migration-and-golden-evidence-required",
}


def test_v1_02a_persistence_read_floors_are_exact() -> None:
    assert V1_PERSISTENCE_VERSION_FLOORS == EXPECTED_FLOORS


def test_v1_02a_current_writer_versions_are_exact() -> None:
    assert V1_PERSISTENCE_CURRENT_WRITE_VERSIONS == EXPECTED_CURRENT_WRITERS


def test_v1_02a_persistence_evolution_rules_are_exact() -> None:
    assert V1_PERSISTENCE_COMPATIBILITY_RULES == EXPECTED_RULES


def test_v1_02a_runtime_versions_match_the_contract() -> None:
    assert SQLITE_RUNTIME_SCHEMA_VERSION == 8
    assert POSTGRES_RUNTIME_SCHEMA_VERSION == 1
    assert SQL_VALUE_CODEC_VERSION == 1
    assert SCHEDULE_DEFINITION_CODEC_VERSION == 3
    assert TRIGGER_CODEC_VERSION == 1
    assert CALENDAR_VALUE_CODEC_VERSION == 1
    assert CALENDAR_COLLECTION_CODEC_VERSION == 1
    assert SQLITE_CALENDAR_SCHEMA_VERSION == 1

    assert SQLITE_SCHEMA_VERSION == SQLITE_RUNTIME_SCHEMA_VERSION
    assert POSTGRES_SCHEMA_VERSION == POSTGRES_RUNTIME_SCHEMA_VERSION
    assert _CODEC_VERSION == SQL_VALUE_CODEC_VERSION
    assert _SCHEDULE_DEFINITION_CODEC_VERSION == SCHEDULE_DEFINITION_CODEC_VERSION
    assert _TRIGGER_CODEC_VERSION == TRIGGER_CODEC_VERSION
    assert _CALENDAR_CODEC_VERSION == CALENDAR_VALUE_CODEC_VERSION
    assert _CALENDAR_COLLECTION_CODEC_VERSION == CALENDAR_COLLECTION_CODEC_VERSION
    assert SqliteCalendarProvider._SCHEMA_VERSION == SQLITE_CALENDAR_SCHEMA_VERSION


def test_v1_02a_every_writer_is_at_or_above_the_frozen_floor() -> None:
    assert set(V1_PERSISTENCE_VERSION_FLOORS) == set(V1_PERSISTENCE_CURRENT_WRITE_VERSIONS)
    for surface, floor in V1_PERSISTENCE_VERSION_FLOORS.items():
        assert V1_PERSISTENCE_CURRENT_WRITE_VERSIONS[surface] >= floor
