"""POST-04 acceptance and fitness tests for installed-package dogfooding."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOGFOOD = REPO_ROOT / "dogfood" / "consumer_app.py"
DISTRIBUTION_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "distribution.yml"


def test_dogfood_consumer_runs_successfully_from_outside_repo(tmp_path: Path) -> None:
    completed = subprocess.run(
        [sys.executable, str(DOGFOOD)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "dogfood-ok" in completed.stdout
    assert "attempts=2" in completed.stdout
    assert "persisted=True" in completed.stdout
    assert "ready=True" in completed.stdout
    assert "state=active" in completed.stdout
    assert completed.stderr == ""


def test_dogfood_consumer_uses_only_stable_pyschedulekit_root_imports() -> None:
    tree = ast.parse(DOGFOOD.read_text(encoding="utf-8"))
    framework_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("pyschedulekit")
    }

    assert framework_modules == {"pyschedulekit"}


def test_distribution_matrix_runs_dogfood_after_install_from_tmp() -> None:
    workflow = DISTRIBUTION_WORKFLOW.read_text(encoding="utf-8")
    clean_install = workflow.split("  clean-install:", 1)[1]

    assert "Dogfood installed package as external consumer" in clean_install
    assert 'python "$GITHUB_WORKSPACE/dogfood/consumer_app.py"' in clean_install

    dogfood_step = clean_install.split(
        "- name: Dogfood installed package as external consumer",
        1,
    )[1]
    assert "cd /tmp" in dogfood_step
