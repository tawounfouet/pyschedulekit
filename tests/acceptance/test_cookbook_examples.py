"""POST-02 acceptance tests for executable cookbook examples."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = REPO_ROOT / "examples"
EXAMPLES = tuple(
    path
    for path in sorted(EXAMPLES_DIR.glob("*.py"))
    if path.name != "__init__.py"
)


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda path: path.stem)
def test_cookbook_example_executes_successfully(example: Path) -> None:
    runpy.run_path(str(example), run_name="__main__")
