"""PG-05 executable PostgreSQL support-matrix contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_postgres_ci_qualifies_supported_major_versions() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "postgres.yml").read_text(encoding="utf-8")

    assert 'postgres: ["16", "17", "18"]' in workflow
    assert "postgres:${{ matrix.postgres }}-alpine" in workflow
    assert "PostgreSQL ${{ matrix.postgres }} adapter qualification" in workflow
    assert '"tests/integration/infrastructure/test_adapter_parity.py"' in workflow
