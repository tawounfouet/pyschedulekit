"""Fitness tests for installed-distribution dogfooding."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "distribution.yml"


def test_distribution_clean_install_runs_consumer_dogfood() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "Dogfood installed package as external consumer" in workflow
    assert 'PYSCHEDULEKIT_DOGFOOD_REQUIRE_INSTALLED: "1"' in workflow
    assert "cd /tmp" in workflow
    assert 'python "$GITHUB_WORKSPACE/dogfood/consumer_app.py"' in workflow


def test_dogfood_script_exists_in_repository() -> None:
    assert (REPO_ROOT / "dogfood" / "consumer_app.py").is_file()
