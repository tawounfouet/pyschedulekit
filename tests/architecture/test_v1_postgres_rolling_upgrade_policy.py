"""V1-02.E executable PostgreSQL evolution / rolling-upgrade policy."""

from __future__ import annotations

from pathlib import Path

from pyschedulekit.infrastructure.persistence_versions import (
    POSTGRES_RUNTIME_SCHEMA_VERSION,
    V1_POSTGRES_ROLLING_UPGRADE_GATES,
    V1_POSTGRES_ROLLING_UPGRADE_POLICY,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_POLICY = {
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

EXPECTED_GATES = (
    "concurrent-schema-bootstrap",
    "same-contract-cross-worker-read-write",
    "fencing-generation-monotonicity",
    "stale-owner-rejection-after-takeover",
    "unknown-future-schema-fail-closed",
    "postgres-16-17-18-live-qualification",
)


def test_v1_02e_postgres_schema_is_still_v1() -> None:
    assert POSTGRES_RUNTIME_SCHEMA_VERSION == 1


def test_v1_02e_rolling_upgrade_policy_is_exact() -> None:
    assert V1_POSTGRES_ROLLING_UPGRADE_POLICY == EXPECTED_POLICY
    assert V1_POSTGRES_ROLLING_UPGRADE_GATES == EXPECTED_GATES


def test_v1_02e_policy_is_documented_on_canonical_surfaces() -> None:
    canonical = (
        REPO_ROOT / "docs" / "v1" / "V1-02E_POSTGRES_EVOLUTION_AND_ROLLING_UPGRADE.md"
    )
    support = REPO_ROOT / "docs" / "postgres" / "SUPPORT_AND_MIGRATION.md"
    v1_readme = REPO_ROOT / "docs" / "v1" / "README.md"
    agents = REPO_ROOT / "AGENTS.md"

    for path in (canonical, support, v1_readme, agents):
        text = path.read_text(encoding="utf-8")
        assert "V1-02.E" in text
        assert "PostgreSQL" in text

    canonical_text = canonical.read_text(encoding="utf-8")
    assert "same-contract workers" in canonical_text
    assert "adjacent release pair" in canonical_text
    assert "backup → drain → migrate → deploy → verify → resume" in canonical_text
    assert "expand → migrate → contract" in canonical_text
    assert "bidirectional readability" in canonical_text
    assert "PostgreSQL 16/17/18" in canonical_text
