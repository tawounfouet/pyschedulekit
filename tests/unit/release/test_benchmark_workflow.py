"""Fitness tests for the manual performance benchmark workflow."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "benchmarks.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_benchmark_workflow_is_manual_only() -> None:
    workflow = _workflow_text()

    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "push:" not in workflow
    assert "schedule:" not in workflow


def test_benchmark_workflow_has_no_performance_threshold_gate() -> None:
    workflow = _workflow_text()

    assert "benchmarks/run.py" in workflow
    assert "--json-out benchmark-results.json" in workflow
    assert "--markdown-out benchmark-results.md" in workflow
    assert "fail-under" not in workflow
    assert "regression-threshold" not in workflow
    assert "baseline-threshold" not in workflow


def test_benchmark_workflow_retains_machine_and_human_readable_evidence() -> None:
    workflow = _workflow_text()

    assert "benchmark-results.json" in workflow
    assert "benchmark-results.md" in workflow
    assert "GITHUB_STEP_SUMMARY" in workflow
    assert "actions/upload-artifact@" in workflow
