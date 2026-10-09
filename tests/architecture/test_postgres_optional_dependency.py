"""Architecture contract for optional PostgreSQL support."""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_postgres_driver_is_optional_and_base_runtime_remains_dependency_free() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]

    assert project["dependencies"] == []

    postgres = project["optional-dependencies"]["postgres"]
    assert postgres == ["psycopg[binary]>=3.3.6,<4"]

    dev = project["optional-dependencies"]["dev"]
    assert "psycopg[binary]>=3.3.6,<4" in dev
