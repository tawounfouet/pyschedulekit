"""Internal persistence-version contract for the PyScheduleKit 1.x line.

This module is intentionally dependency-neutral so compatibility tooling can inspect the
complete persistence contract without importing optional PostgreSQL dependencies.
"""

SQLITE_RUNTIME_SCHEMA_VERSION = 8
POSTGRES_RUNTIME_SCHEMA_VERSION = 1
SQL_VALUE_CODEC_VERSION = 1
SCHEDULE_DEFINITION_CODEC_VERSION = 3
TRIGGER_CODEC_VERSION = 1
CALENDAR_VALUE_CODEC_VERSION = 1
CALENDAR_COLLECTION_CODEC_VERSION = 1
SQLITE_CALENDAR_SCHEMA_VERSION = 1

V1_PERSISTENCE_VERSION_FLOORS = {
    "calendar-collection-codec": 1,
    "calendar-value-codec": 1,
    "postgres-runtime-schema": 1,
    "schedule-definition-codec": 1,
    "sql-value-codec": 1,
    "sqlite-calendar-schema": 1,
    "sqlite-runtime-schema": 1,
    "trigger-envelope-codec": 1,
}

V1_PERSISTENCE_CURRENT_WRITE_VERSIONS = {
    "calendar-collection-codec": CALENDAR_COLLECTION_CODEC_VERSION,
    "calendar-value-codec": CALENDAR_VALUE_CODEC_VERSION,
    "postgres-runtime-schema": POSTGRES_RUNTIME_SCHEMA_VERSION,
    "schedule-definition-codec": SCHEDULE_DEFINITION_CODEC_VERSION,
    "sql-value-codec": SQL_VALUE_CODEC_VERSION,
    "sqlite-calendar-schema": SQLITE_CALENDAR_SCHEMA_VERSION,
    "sqlite-runtime-schema": SQLITE_RUNTIME_SCHEMA_VERSION,
    "trigger-envelope-codec": TRIGGER_CODEC_VERSION,
}

V1_PERSISTENCE_COMPATIBILITY_RULES = {
    "cross-adapter-data-migration": "unsupported",
    "downgrade-readability": "not-guaranteed",
    "future-version-policy": "fail-closed",
    "mixed-version-workers": "explicit-overlap-qualification-required",
    "read-floor-lifetime": "frozen-through-1.x",
    "schema-upgrade-backup": "required-before-format-changing-upgrade",
    "writer-evolution": "forward-migration-and-golden-evidence-required",
}
