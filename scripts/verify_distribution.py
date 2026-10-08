"""Validate built PyScheduleKit distributions before publication."""

from __future__ import annotations

import argparse
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path

from pyschedulekit import __version__

PROJECT_NAME = "pyschedulekit"


class DistributionValidationError(RuntimeError):
    """Raised when a built distribution violates the release contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DistributionValidationError(message)


def _single(paths: list[Path], *, kind: str) -> Path:
    _require(len(paths) == 1, f"Expected exactly one {kind}, found {len(paths)}.")
    return paths[0]


def _validate_wheel(dist_dir: Path) -> Path:
    wheel = _single(sorted(dist_dir.glob("*.whl")), kind="wheel")
    expected_name = f"{PROJECT_NAME}-{__version__}-py3-none-any.whl"
    _require(
        wheel.name == expected_name,
        f"Unexpected wheel name: {wheel.name!r}; expected {expected_name!r}.",
    )

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        required = {
            "pyschedulekit/__init__.py",
            "pyschedulekit/_version.py",
            "pyschedulekit/py.typed",
        }
        missing = sorted(required - names)
        _require(not missing, f"Wheel is missing required package files: {missing!r}.")

        metadata_paths = sorted(name for name in names if name.endswith(".dist-info/METADATA"))
        metadata_path = _single(
            [Path(name) for name in metadata_paths],
            kind="wheel METADATA file",
        )
        metadata = Parser().parsestr(archive.read(metadata_path.as_posix()).decode("utf-8"))

    _require(metadata.get("Name") == PROJECT_NAME, "Wheel metadata has an unexpected Name.")
    _require(metadata.get("Version") == __version__, "Wheel metadata version does not match runtime.")
    _require(
        metadata.get("Requires-Python") == ">=3.11",
        "Wheel metadata must declare Requires-Python >=3.11.",
    )
    return wheel


def _validate_sdist(dist_dir: Path) -> Path:
    sdist = _single(sorted(dist_dir.glob("*.tar.gz")), kind="source distribution")
    expected_name = f"{PROJECT_NAME}-{__version__}.tar.gz"
    _require(
        sdist.name == expected_name,
        f"Unexpected sdist name: {sdist.name!r}; expected {expected_name!r}.",
    )

    prefix = f"{PROJECT_NAME}-{__version__}"
    required = {
        f"{prefix}/LICENSE",
        f"{prefix}/README.md",
        f"{prefix}/pyproject.toml",
        f"{prefix}/src/pyschedulekit/__init__.py",
        f"{prefix}/src/pyschedulekit/_version.py",
        f"{prefix}/src/pyschedulekit/py.typed",
    }

    with tarfile.open(sdist, mode="r:gz") as archive:
        names = set(archive.getnames())

    missing = sorted(required - names)
    _require(not missing, f"Source distribution is missing required files: {missing!r}.")
    _require(
        all(name == prefix or name.startswith(f"{prefix}/") for name in names),
        "Source distribution contains entries outside its canonical top-level directory.",
    )
    return sdist


def validate(dist_dir: Path) -> tuple[Path, Path]:
    _require(dist_dir.is_dir(), f"Distribution directory does not exist: {dist_dir}")
    wheel = _validate_wheel(dist_dir)
    sdist = _validate_sdist(dist_dir)
    return wheel, sdist


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dist_dir", type=Path, nargs="?", default=Path("dist"))
    args = parser.parse_args()

    wheel, sdist = validate(args.dist_dir)
    print(f"Validated wheel: {wheel.name}")
    print(f"Validated sdist: {sdist.name}")
    print(f"Distribution contract OK for PyScheduleKit {__version__}.")


if __name__ == "__main__":
    main()
