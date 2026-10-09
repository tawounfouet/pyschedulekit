"""Coverage ownership for the optional PostgreSQL adapter."""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_base_coverage_excludes_optional_postgres_modules() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    omitted = set(pyproject["tool"]["coverage"]["run"]["omit"])

    assert omitted == {
        "src/pyschedulekit/infrastructure/postgres.py",
        "src/pyschedulekit/infrastructure/postgres_schema.py",
    }
    assert pyproject["tool"]["coverage"]["report"]["fail_under"] == 85


def test_postgres_workflow_owns_adapter_coverage() -> None:
    config = (REPO_ROOT / ".coveragerc-postgres").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github" / "workflows" / "postgres.yml").read_text(
        encoding="utf-8"
    )

    assert "fail_under = 60" in config
    assert "pyschedulekit.infrastructure.postgres" in config
    assert "pyschedulekit.infrastructure.postgres_schema" in config
    assert "--cov=pyschedulekit.infrastructure.postgres" in workflow
    assert "--cov=pyschedulekit.infrastructure.postgres_schema" in workflow
    assert "--cov-config=.coveragerc-postgres" in workflow
