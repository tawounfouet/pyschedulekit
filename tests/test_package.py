"""Package-level smoke tests."""

from importlib.metadata import version

from pyschedulekit import __version__


def test_package_exposes_initial_version() -> None:
    assert __version__ == "0.1.0a1"


def test_package_version_matches_distribution_metadata() -> None:
    assert __version__ == version("pyschedulekit")
