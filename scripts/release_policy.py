"""Publication policy for PyScheduleKit release candidates."""

from __future__ import annotations

import argparse
import re

_STABLE_PUBLIC_VERSION = re.compile(
    r"^(?P<major>[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$"
)


def should_publish_to_pypi(version: str) -> bool:
    """Return whether one source version is eligible for public PyPI publication."""

    match = _STABLE_PUBLIC_VERSION.fullmatch(version)
    if match is None:
        return False

    return int(match.group("major")) >= 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    value = "true" if should_publish_to_pypi(args.version) else "false"
    print(value)


if __name__ == "__main__":
    main()
