"""POST-06 qualification for the deterministic chaos campaign."""

from __future__ import annotations

import json
from pathlib import Path

from chaos.run import SCENARIOS, assert_campaign_passed, run_campaign

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "chaos.yml"


def test_chaos_campaign_passes_all_declared_scenarios() -> None:
    report = run_campaign()

    assert report["schema_version"] == 1
    assert report["deterministic"] is True
    assert report["scenario_count"] == len(SCENARIOS) == 5
    assert report["passed"] == 5
    assert report["failed"] == 0

    scenarios = report["scenarios"]
    assert isinstance(scenarios, list)
    assert {scenario["name"] for scenario in scenarios} == {
        "executor_retry_recovery",
        "outbox_broker_recovery",
        "runtime_cycle_supervision",
        "admission_conflict_compensation",
        "stale_owner_fencing",
    }
    assert all(scenario["passed"] for scenario in scenarios)

    # Report must remain JSON serializable for workflow artifact retention.
    assert json.loads(json.dumps(report))["failed"] == 0
    assert_campaign_passed(report)


def test_chaos_workflow_is_deterministic_and_evidence_oriented() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "push:" in workflow
    assert "- main" in workflow
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "schedule:" not in workflow
    assert "python -m chaos.run --output chaos-results.json" in workflow
    assert "name: chaos-results" in workflow
    assert "retention-days: 30" in workflow
