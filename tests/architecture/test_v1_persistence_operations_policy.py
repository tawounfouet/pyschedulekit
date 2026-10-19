"""V1-02.F executable persistence backup / rollback / operations policy."""

from __future__ import annotations

from pathlib import Path

from pyschedulekit.infrastructure.persistence_versions import (
    V1_PERSISTENCE_OPERATIONS_GATES,
    V1_PERSISTENCE_OPERATIONS_POLICY,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_POLICY = {
    "backup-before-format-change": "required",
    "backup-integrity-verification": "required",
    "go-no-go": "explicit-preflight-and-postflight-gates",
    "migration-interruption": "transactional-step-or-fail-closed",
    "postgres-backup": "native-postgres-backup-required",
    "postgres-restore-rehearsal": "pg-dump-pg-restore-live-ci",
    "restore-rehearsal-before-release": "required",
    "rollback-mode": "restore-known-good-backup-not-in-place-downgrade",
    "rpo-rto": "application-owned",
    "sqlite-backup": "sqlite-backup-api-or-consistent-offline-copy",
    "post-restore-verification": "schema-integrity-domain-smoke-required",
}

EXPECTED_GATES = (
    "backup-artifact-created",
    "backup-integrity-verified",
    "restore-rehearsal-passed",
    "sqlite-interrupted-migration-rollback",
    "post-restore-schema-verification",
    "post-restore-domain-smoke",
    "postgres-16-17-18-backup-restore-rehearsal",
    "explicit-go-abort-criteria",
)


def test_v1_02f_operations_policy_is_exact() -> None:
    assert V1_PERSISTENCE_OPERATIONS_POLICY == EXPECTED_POLICY
    assert V1_PERSISTENCE_OPERATIONS_GATES == EXPECTED_GATES


def test_v1_02f_operations_contract_is_documented_and_rehearsed() -> None:
    canonical = REPO_ROOT / "docs" / "v1" / "V1-02F_BACKUP_ROLLBACK_OPERATIONS_CONTRACT.md"
    runbook = REPO_ROOT / "docs" / "operations" / "PERSISTENCE_BACKUP_RESTORE_RUNBOOK.md"
    pg_script = REPO_ROOT / "scripts" / "qualification" / "postgres_backup_restore_rehearsal.sh"
    pg_probe = REPO_ROOT / "scripts" / "qualification" / "postgres_backup_restore_probe.py"
    workflow = REPO_ROOT / ".github" / "workflows" / "postgres.yml"

    for path in (canonical, runbook, pg_script, pg_probe, workflow):
        assert path.is_file()

    canonical_text = canonical.read_text(encoding="utf-8").lower()
    for phrase in (
        "backup → verify → migrate",
        "restore-known-good-backup",
        "go criteria",
        "abort criteria",
        "no in-place downgrade",
        "postgresql 16/17/18",
        "sqlite",
    ):
        assert phrase in canonical_text

    runbook_text = runbook.read_text(encoding="utf-8")
    assert "sqlite3.backup()" in runbook_text
    assert "pg_dump" in runbook_text
    assert "pg_restore" in runbook_text
    assert "RPO/RTO" in runbook_text

    workflow_text = workflow.read_text(encoding="utf-8")
    assert "postgres_backup_restore_rehearsal.sh" in workflow_text
    assert "PYSCHEDULEKIT_TEST_POSTGRES_MAJOR" in workflow_text
