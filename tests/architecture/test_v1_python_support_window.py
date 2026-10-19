"""V1-03.A executable Python support-window contract."""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
DISTRIBUTION = REPO_ROOT / ".github" / "workflows" / "distribution.yml"

EXPECTED_MINORS = ("3.11", "3.12", "3.13", "3.14")
EXPECTED_REQUIRES_PYTHON = ">=3.11,<3.15"


def test_v1_03a_pyproject_declares_exact_support_window() -> None:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = data["project"]
    platform = data["tool"]["pyschedulekit"]["platform"]

    assert project["requires-python"] == EXPECTED_REQUIRES_PYTHON
    assert tuple(platform["supported-python-minors"]) == EXPECTED_MINORS
    assert platform["newest-supported-python"] == "3.14"

    classifiers = set(project["classifiers"])
    for version in EXPECTED_MINORS:
        assert f"Programming Language :: Python :: {version}" in classifiers


def test_v1_03a_ci_qualifies_every_supported_python_minor() -> None:
    workflow = CI.read_text(encoding="utf-8")

    for version in EXPECTED_MINORS:
        assert f'- "{version}"' in workflow


def test_v1_03a_distribution_qualifies_every_supported_python_minor() -> None:
    workflow = DISTRIBUTION.read_text(encoding="utf-8")

    for version in EXPECTED_MINORS:
        assert f'- "{version}"' in workflow

    assert "wheel" in workflow
    assert "sdist" in workflow
