"""Acceptance qualification for the runnable cookbook examples."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

EXAMPLES = (
    ("examples/01_interval_quickstart.py", "interval quickstart: heartbeat executed once"),
    ("examples/02_cron_timezone.py", "cron timezone: Paris weekday 09:00 executed"),
    (
        "examples/03_retry_backoff.py",
        "retry backoff: transient failure recovered on attempt 2",
    ),
    (
        "examples/04_sqlite_durability.py",
        "sqlite durability: schedule survived database reopen",
    ),
    (
        "examples/05_operational_health.py",
        "operational health: scheduler is ready after startup barriers",
    ),
    (
        "examples/06_composite_any_of.py",
        "composite any-of: shared occurrence executed once",
    ),
)


@pytest.mark.parametrize(("relative_path", "expected_output"), EXAMPLES)
def test_cookbook_example_runs_successfully(
    relative_path: str,
    expected_output: str,
) -> None:
    completed = subprocess.run(
        [sys.executable, relative_path],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert expected_output in completed.stdout
    assert completed.stderr == ""
