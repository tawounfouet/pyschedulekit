"""Smoke qualification for the benchmark harness."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_benchmark_smoke_profile_produces_structured_results(tmp_path: Path) -> None:
    json_output = tmp_path / "benchmarks.json"
    markdown_output = tmp_path / "benchmarks.md"

    subprocess.run(
        [
            sys.executable,
            "benchmarks/run.py",
            "--profile",
            "smoke",
            "--json-out",
            str(json_output),
            "--markdown-out",
            str(markdown_output),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    report = json.loads(json_output.read_text(encoding="utf-8"))

    assert report["schema_version"] == 2
    assert report["profile"] == "smoke"
    assert report["pyschedulekit_version"]

    results = {result["name"]: result for result in report["results"]}
    assert set(results) == {
        "cron_next_after",
        "interval_next_after",
        "run_pending_memory",
        "run_pending_memory_idle_100",
        "run_pending_memory_idle_1000",
        "run_pending_sqlite",
    }

    scaling = report["scaling"]
    assert scaling["memory_idle_small_count"] == 100
    assert scaling["memory_idle_large_count"] == 1000
    assert scaling["memory_idle_large_to_small_ratio"] > 0

    for result in results.values():
        assert result["operations"] > 0
        assert result["repeats"] == 2
        assert result["median_seconds"] >= 0
        assert result["min_seconds"] >= 0
        assert result["max_seconds"] >= result["min_seconds"]
        assert result["operations_per_second"] > 0

    markdown = markdown_output.read_text(encoding="utf-8")
    assert "# PyScheduleKit Benchmark Report" in markdown
    assert "## Scale evidence" in markdown
    assert "Benchmark numbers are evidence, not CI pass/fail thresholds." in markdown


def test_benchmark_workflow_records_standard_baseline_after_main_merge() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "benchmarks.yml").read_text(encoding="utf-8")

    assert "push:" in workflow
    assert "branches:" in workflow
    assert "- main" in workflow
    assert "${{ inputs.profile || 'standard' }}" in workflow
    assert "${{ inputs.python_version || '3.13' }}" in workflow
    assert "retention-days: 30" in workflow
