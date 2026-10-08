"""REL-08 tests for release readiness preflight."""

from pathlib import Path

import pytest
from scripts.release_preflight import (
    ExternalReadiness,
    ReleasePreflightError,
    validate_release_preflight,
)


def _ready() -> ExternalReadiness:
    return ExternalReadiness(
        testpypi_trusted_publisher=True,
        pypi_trusted_publisher=True,
        immutable_releases=True,
    )


def test_t_release_preflight_001_accepts_matching_release_and_frozen_changelog(
    tmp_path: Path,
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n## [0.1.0a1] - 2026-10-08\n\n### Added\n\n- Release.\n",
        encoding="utf-8",
    )

    assert (
        validate_release_preflight(
            release_tag="v0.1.0a1",
            changelog=changelog,
            readiness=_ready(),
            package_version="0.1.0a1",
        )
        == "0.1.0a1"
    )


def test_t_release_preflight_002_rejects_version_mismatch(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("## [0.1.0a1] - 2026-10-08\n", encoding="utf-8")

    with pytest.raises(ReleasePreflightError, match="does not match"):
        validate_release_preflight(
            release_tag="v0.1.0a2",
            changelog=changelog,
            readiness=_ready(),
            package_version="0.1.0a1",
        )


def test_t_release_preflight_003_rejects_unfrozen_changelog(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## [Unreleased]\n", encoding="utf-8")

    with pytest.raises(ReleasePreflightError, match="dated release heading"):
        validate_release_preflight(
            release_tag="v0.1.0a1",
            changelog=changelog,
            readiness=_ready(),
            package_version="0.1.0a1",
        )


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("testpypi_trusted_publisher", "TestPyPI Trusted Publisher"),
        ("pypi_trusted_publisher", "PyPI Trusted Publisher"),
        ("immutable_releases", "GitHub Immutable Releases"),
    ],
)
def test_t_release_preflight_004_rejects_missing_external_acknowledgement(
    tmp_path: Path,
    field: str,
    expected: str,
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("## [0.1.0a1] - 2026-10-08\n", encoding="utf-8")

    values = {
        "testpypi_trusted_publisher": True,
        "pypi_trusted_publisher": True,
        "immutable_releases": True,
    }
    values[field] = False

    with pytest.raises(ReleasePreflightError, match=expected):
        validate_release_preflight(
            release_tag="v0.1.0a1",
            changelog=changelog,
            readiness=ExternalReadiness(**values),
            package_version="0.1.0a1",
        )
