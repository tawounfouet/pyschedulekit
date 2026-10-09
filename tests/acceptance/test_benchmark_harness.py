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

    assert report["schema_version"] == 1
    assert report["profile"] == "smoke"
    assert report["pyschedulekit_version"]

    results = {result["name"]: result for result in report["results"]}
    assert set(results) == {
        "cron_next_after",
        "interval_next_after",
        "run_pending_memory",
        "run_pending_sqlite",
    }

    for result in results.values():
        assert result["operations"] > 0
        assert result["repeats"] == 2
        assert result["median_seconds"] >= 0
        assert result["min_seconds"] >= 0
        assert result["max_seconds"] >= result["min_seconds"]
        assert result["operations_per_second"] > 0

    markdown = markdown_output.read_text(encoding="utf-8")
    assert "# PyScheduleKit Benchmark Report" in markdown
    assert "Benchmark numbers are evidence, not CI pass/fail thresholds." in markdown
