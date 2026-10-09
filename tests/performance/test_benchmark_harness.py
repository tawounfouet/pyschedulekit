"""POST-05 qualification for the performance baseline harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.run_baseline import assert_guardrails, run_baseline

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "performance.yml"


def test_smoke_baseline_produces_machine_readable_metrics() -> None:
    results = run_baseline("smoke")

    assert results["schema_version"] == 1
    assert results["profile"] == "smoke"

    interval = results["interval_next_after"]
    idle = results["idle_scheduler_cycle"]
    assert isinstance(interval, dict)
    assert isinstance(idle, dict)

    assert float(interval["far_to_near_ratio"]) > 0
    assert set(idle["results"]) == {"100", "1000"}

    rendered = json.dumps(results)
    assert '"schema_version": 1' in rendered


def test_guardrails_reject_catastrophic_complexity_ratios() -> None:
    results = {
        "interval_next_after": {
            "far_to_near_ratio": 1000.0,
        },
        "idle_scheduler_cycle": {
            "ten_k_to_one_k_ratio": 1.0,
        },
    }

    with pytest.raises(AssertionError, match="IntervalTrigger"):
        assert_guardrails(results)


def test_performance_workflow_runs_ci_profile_and_uploads_json() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "python -m benchmarks.run_baseline" in workflow
    assert "--profile ci" in workflow
    assert "--assert-guardrails" in workflow
    assert "--output benchmark-results.json" in workflow
    assert "name: performance-baseline" in workflow
    assert "retention-days: 30" in workflow
