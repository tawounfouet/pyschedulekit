"""Documentation contract for the stable PyScheduleKit public API."""

from pathlib import Path

from pyschedulekit.api._manifest import EXPERIMENTAL_PUBLIC_NAMES, STABLE_PUBLIC_NAMES

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DOC = REPO_ROOT / "docs" / "api" / "README.md"


def test_every_stable_public_name_is_documented() -> None:
    text = API_DOC.read_text(encoding="utf-8")

    missing = [name for name in STABLE_PUBLIC_NAMES if f"`{name}`" not in text]

    assert not missing, f"Stable public names missing from API docs: {missing}"


def test_every_experimental_name_is_documented_outside_the_stable_root() -> None:
    text = API_DOC.read_text(encoding="utf-8")
    experimental_section = text.split("## Experimental coordination names", 1)[1].split(
        "## Testing helpers",
        1,
    )[0]

    missing = [
        name for name in EXPERIMENTAL_PUBLIC_NAMES if f"`{name}`" not in experimental_section
    ]

    assert not missing, f"Experimental names missing from API docs: {missing}"
