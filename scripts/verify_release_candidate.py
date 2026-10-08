"""Validate one tagged PyScheduleKit release candidate."""

from __future__ import annotations

import argparse
from pathlib import Path

from pyschedulekit import __version__

from verify_distribution import validate as validate_distribution


class ReleaseCandidateValidationError(RuntimeError):
    """Raised when tag, source version, and built artifacts do not agree."""


def release_version_from_tag(release_tag: str) -> str:
    """Return the exact package version encoded by one canonical Git tag."""

    if not release_tag.startswith("v"):
        raise ReleaseCandidateValidationError(
            f"Release tag must start with 'v'; received {release_tag!r}."
        )

    version = release_tag[1:]
    if not version:
        raise ReleaseCandidateValidationError("Release tag must include a version after 'v'.")

    if release_tag != release_tag.strip():
        raise ReleaseCandidateValidationError("Release tag must not contain surrounding whitespace.")

    return version


def validate_release_candidate(
    *,
    release_tag: str,
    dist_dir: Path,
    package_version: str = __version__,
) -> tuple[Path, Path]:
    """Validate tag/source version identity and the corresponding distributions."""

    tag_version = release_version_from_tag(release_tag)
    if tag_version != package_version:
        raise ReleaseCandidateValidationError(
            "Release tag version does not match the source package version: "
            f"tag={tag_version!r}, package={package_version!r}."
        )

    wheel, sdist = validate_distribution(dist_dir)
    return wheel, sdist


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("dist_dir", type=Path, nargs="?", default=Path("dist"))
    args = parser.parse_args()

    wheel, sdist = validate_release_candidate(
        release_tag=args.release_tag,
        dist_dir=args.dist_dir,
    )
    print(f"Release tag: {args.release_tag}")
    print(f"Source version: {__version__}")
    print(f"Qualified wheel: {wheel.name}")
    print(f"Qualified sdist: {sdist.name}")
    print("Release candidate version gate passed.")


if __name__ == "__main__":
    main()
