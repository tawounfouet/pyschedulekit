"""V1-02.G final persistence compatibility review."""

from __future__ import annotations

from pathlib import Path

from pyschedulekit.infrastructure.persistence_versions import (
    V1_PERSISTENCE_COMPATIBILITY_RULES,
    V1_PERSISTENCE_CURRENT_WRITE_VERSIONS,
    V1_PERSISTENCE_OPERATIONS_GATES,
    V1_PERSISTENCE_OPERATIONS_POLICY,
    V1_PERSISTENCE_VERSION_FLOORS,
    V1_POSTGRES_ROLLING_UPGRADE_GATES,
    V1_POSTGRES_ROLLING_UPGRADE_POLICY,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

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

EXPECTED_WRITERS = {
    "calendar-collection-codec": 1,
    "calendar-value-codec": 1,
    "postgres-runtime-schema": 1,
    "schedule-definition-codec": 3,
    "sql-value-codec": 1,
    "sqlite-calendar-schema": 1,
    "sqlite-runtime-schema": 8,
    "trigger-envelope-codec": 1,
}

REQUIRED_V1_02_DOCS = (
    "V1-02A_PERSISTENCE_VERSION_FLOOR_AND_POLICY.md",
    "V1-02B_IMMUTABLE_GOLDEN_COMPATIBILITY_FIXTURES.md",
    "V1-02C_SQLITE_FORWARD_MIGRATION_QUALIFICATION.md",
    "V1-02D_CODEC_MIGRATION_AND_SEMANTIC_EQUIVALENCE.md",
    "V1-02E_POSTGRES_EVOLUTION_AND_ROLLING_UPGRADE.md",
    "V1-02F_BACKUP_ROLLBACK_OPERATIONS_CONTRACT.md",
    "V1-02G_FINAL_PERSISTENCE_COMPATIBILITY_REVIEW.md",
)

REQUIRED_EVIDENCE = (
    "tests/compatibility/test_v1_golden_persistence_fixtures.py",
    "tests/compatibility/test_v1_sqlite_forward_migrations.py",
    "tests/compatibility/test_v1_codec_semantic_equivalence.py",
    "tests/compatibility/test_v1_sqlite_backup_restore_operations.py",
    "tests/integration/postgres/test_v1_postgres_rolling_upgrade.py",
    "tests/unit/infrastructure/test_calendar_provider.py",
    "scripts/qualification/postgres_backup_restore_probe.py",
    "scripts/qualification/postgres_backup_restore_rehearsal.sh",
    "docs/operations/PERSISTENCE_BACKUP_RESTORE_RUNBOOK.md",
)


def test_v1_02g_persistence_floor_and_writer_matrix_is_closed() -> None:
    assert V1_PERSISTENCE_VERSION_FLOORS == EXPECTED_FLOORS
    assert V1_PERSISTENCE_CURRENT_WRITE_VERSIONS == EXPECTED_WRITERS
    assert V1_PERSISTENCE_VERSION_FLOORS.keys() == V1_PERSISTENCE_CURRENT_WRITE_VERSIONS.keys()

    for surface, floor in V1_PERSISTENCE_VERSION_FLOORS.items():
        assert floor <= V1_PERSISTENCE_CURRENT_WRITE_VERSIONS[surface]


def test_v1_02g_compatibility_rules_cover_the_full_1x_persistence_boundary() -> None:
    assert V1_PERSISTENCE_COMPATIBILITY_RULES == {
        "cross-adapter-data-migration": "unsupported",
        "downgrade-readability": "not-guaranteed",
        "future-version-policy": "fail-closed",
        "mixed-version-workers": "explicit-overlap-qualification-required",
        "read-floor-lifetime": "frozen-through-1.x",
        "schema-upgrade-backup": "required-before-format-changing-upgrade",
        "writer-evolution": "forward-migration-and-golden-evidence-required",
    }

    assert V1_POSTGRES_ROLLING_UPGRADE_POLICY["schema-change-default"] == (
        "drain-workers-before-migration"
    )
    assert V1_POSTGRES_ROLLING_UPGRADE_POLICY["writer-reader-overlap"] == (
        "bidirectional-readability-required"
    )
    assert V1_POSTGRES_ROLLING_UPGRADE_POLICY["contract-ddl-during-overlap"] == "forbidden"
    assert "postgres-16-17-18-live-qualification" in V1_POSTGRES_ROLLING_UPGRADE_GATES

    assert V1_PERSISTENCE_OPERATIONS_POLICY["rollback-mode"] == (
        "restore-known-good-backup-not-in-place-downgrade"
    )
    assert V1_PERSISTENCE_OPERATIONS_POLICY["restore-rehearsal-before-release"] == "required"
    assert "postgres-16-17-18-backup-restore-rehearsal" in V1_PERSISTENCE_OPERATIONS_GATES
    assert "sqlite-interrupted-migration-rollback" in V1_PERSISTENCE_OPERATIONS_GATES


def test_v1_02g_all_persistence_contract_documents_exist() -> None:
    v1_dir = REPO_ROOT / "docs" / "v1"
    for filename in REQUIRED_V1_02_DOCS:
        assert (v1_dir / filename).is_file(), filename


def test_v1_02g_all_required_persistence_evidence_exists() -> None:
    for relative_path in REQUIRED_EVIDENCE:
        assert (REPO_ROOT / relative_path).is_file(), relative_path


def test_v1_02g_readiness_audit_marks_v1_f04_closed() -> None:
    audit = (REPO_ROOT / "docs" / "v1" / "V1-00_READINESS_AUDIT.md").read_text(encoding="utf-8")
    assert "V1-F04 — Persistence compatibility floor lacks a 1.x promise — CLOSED" in audit
    assert "Closed by V1-02.A through V1-02.G" in audit


def test_v1_02g_navigation_closes_v1_02_and_advances_to_v1_03() -> None:
    readme = (REPO_ROOT / "docs" / "v1" / "README.md").read_text(encoding="utf-8")
    assert "V1-02  Persistence Compatibility Contract      COMPLETE" in readme
    assert "V1-03  Platform, Warning and Security Gates    NEXT" in readme
    assert "V1-02.G  Final Persistence Compatibility Review      COMPLETE" in readme

    final_review = (
        REPO_ROOT / "docs" / "v1" / "V1-02G_FINAL_PERSISTENCE_COMPATIBILITY_REVIEW.md"
    ).read_text(encoding="utf-8")
    assert "V1-02 VERDICT: GO" in final_review
    assert "Overall v1.0.0 verdict remains NO-GO" in final_review
