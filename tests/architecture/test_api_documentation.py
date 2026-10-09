"""Documentation contract for the stable PyScheduleKit public API."""

from pathlib import Path

from pyschedulekit.api._manifest import LEGACY_ROOT_NAMES, STABLE_PUBLIC_NAMES

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DOC = REPO_ROOT / "docs" / "api" / "README.md"


def test_every_stable_public_name_is_documented() -> None:
    text = API_DOC.read_text(encoding="utf-8")

    missing = [name for name in STABLE_PUBLIC_NAMES if f"`{name}`" not in text]

    assert not missing, f"Stable public names missing from API docs: {missing}"


def test_every_legacy_root_name_is_documented_as_compatibility_surface() -> None:
    text = API_DOC.read_text(encoding="utf-8")
    legacy_section = text.split("## Legacy root compatibility names", 1)[1].split(
        "## Testing helpers",
        1,
    )[0]

    missing = [name for name in LEGACY_ROOT_NAMES if f"`{name}`" not in legacy_section]

    assert not missing, f"Legacy compatibility names missing from API docs: {missing}"
