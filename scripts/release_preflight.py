"""Repository-local preflight checks for a PyScheduleKit release."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from pyschedulekit import __version__
from scripts.verify_release_candidate import release_version_from_tag


class ReleasePreflightError(RuntimeError):
    """Raised when release-readiness conditions are not satisfied."""


@dataclass(frozen=True, slots=True)
class ExternalReadiness:
    """Operator-confirmed external controls that the repository cannot prove itself."""

    pypi_trusted_publisher: bool
    immutable_releases: bool
    testpypi_trusted_publisher: bool = True

    @property
    def ready(self) -> bool:
        return self.pypi_trusted_publisher and self.immutable_releases


def validate_changelog(path: Path, *, package_version: str) -> None:
    """Require a frozen release heading for the package version."""

    if not path.is_file():
        raise ReleasePreflightError(f"Changelog does not exist: {path}")

    text = path.read_text(encoding="utf-8")
    heading_prefix = f"## [{package_version}] - "
    if heading_prefix not in text:
        raise ReleasePreflightError(
            f"CHANGELOG.md must contain a dated release heading starting with {heading_prefix!r}."
        )


def validate_release_preflight(
    *,
    release_tag: str,
    changelog: Path,
    readiness: ExternalReadiness,
    package_version: str = __version__,
) -> str:
    """Validate all repository-local and acknowledged external release conditions."""

    tag_version = release_version_from_tag(release_tag)
    if tag_version != package_version:
        raise ReleasePreflightError(
            "Release tag does not match the source package version: "
            f"tag={tag_version!r}, package={package_version!r}."
        )

    validate_changelog(changelog, package_version=package_version)

    if not readiness.ready:
        missing = []
        if not readiness.pypi_trusted_publisher:
            missing.append("PyPI Trusted Publisher")
        if not readiness.immutable_releases:
            missing.append("GitHub Immutable Releases")
        raise ReleasePreflightError(
            "External release controls are not acknowledged ready: " + ", ".join(missing)
        )

    return package_version


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    parser.add_argument("--testpypi-trusted-publisher-ready", action="store_true")
    parser.add_argument("--pypi-trusted-publisher-ready", action="store_true")
    parser.add_argument("--immutable-releases-ready", action="store_true")
    args = parser.parse_args()

    version = validate_release_preflight(
        release_tag=args.release_tag,
        changelog=args.changelog,
        readiness=ExternalReadiness(
            testpypi_trusted_publisher=args.testpypi_trusted_publisher_ready,
            pypi_trusted_publisher=args.pypi_trusted_publisher_ready,
            immutable_releases=args.immutable_releases_ready,
        ),
    )

    print(f"Release tag: {args.release_tag}")
    print(f"Source package version: {version}")
    print("Changelog release heading: ready")
    print("TestPyPI Trusted Publisher: acknowledged ready")
    print("PyPI Trusted Publisher: acknowledged ready")
    print("GitHub Immutable Releases: acknowledged ready")
    print("Release preflight passed. This command does not create or push a tag.")


if __name__ == "__main__":
    main()
