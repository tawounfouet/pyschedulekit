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


V1_POSTGRES_ROLLING_UPGRADE_POLICY = {
    "adjacent-release-overlap": "explicit-release-pair-qualification-required",
    "contract-ddl-during-overlap": "forbidden",
    "current-schema-overlap": "same-contract-workers-qualified",
    "future-schema-policy": "fail-closed-until-explicit-migration-exists",
    "migration-order-default": "backup-drain-migrate-deploy-verify-resume",
    "overlap-safe-schema-change": "expand-migrate-contract-required",
    "postgres-major-upgrade": "drain-and-upgrade-outside-framework",
    "schema-bootstrap": "transaction-scoped-advisory-lock",
    "schema-change-default": "drain-workers-before-migration",
    "writer-reader-overlap": "bidirectional-readability-required",
}

V1_POSTGRES_ROLLING_UPGRADE_GATES = (
    "concurrent-schema-bootstrap",
    "same-contract-cross-worker-read-write",
    "fencing-generation-monotonicity",
    "stale-owner-rejection-after-takeover",
    "unknown-future-schema-fail-closed",
    "postgres-16-17-18-live-qualification",
)
