"""POST-00G fitness tests for CI reproducibility and portability."""

from __future__ import annotations

import re
import runpy
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
USES_PATTERN = re.compile(r"^\s*uses:\s*([^\s#]+)", re.MULTILINE)


def test_ci_hardening_001_coverage_floor_is_enforced() -> None:
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert config["tool"]["coverage"]["report"]["fail_under"] >= 85


def test_ci_hardening_002_ruff_version_is_exactly_pinned() -> None:
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev_dependencies = config["project"]["optional-dependencies"]["dev"]

    assert "ruff==0.16.1" in dev_dependencies


def test_ci_hardening_003_external_actions_are_commit_sha_pinned() -> None:
    workflow_paths = sorted((REPO_ROOT / ".github/workflows").glob("*.yml"))
    assert workflow_paths

    for workflow_path in workflow_paths:
        workflow = workflow_path.read_text(encoding="utf-8")
        for reference in USES_PATTERN.findall(workflow):
            if reference.startswith("./"):
                continue
            action, separator, revision = reference.partition("@")
            assert separator, f"{workflow_path}: action reference has no revision: {reference}"
            assert action, f"{workflow_path}: action name is empty: {reference}"
            assert SHA_PATTERN.fullmatch(revision), (
                f"{workflow_path}: action must use a 40-character commit SHA: {reference}"
            )


@pytest.mark.parametrize(
    "relative_path",
    (
        "tests/unit/release/test_pypi_workflow.py",
        "tests/unit/release/test_github_release_workflow.py",
        "tests/unit/release/test_release_readiness_workflow.py",
    ),
)
def test_ci_hardening_004_release_fitness_tests_are_cwd_independent(
    relative_path: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    namespace = runpy.run_path(str(REPO_ROOT / relative_path))
    workflow_text = namespace["_workflow_text"]()

    assert "name:" in workflow_text
