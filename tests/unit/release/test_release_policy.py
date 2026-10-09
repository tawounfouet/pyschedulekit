"""Tests for the public release publication policy."""

import pytest

from scripts.release_policy import should_publish_to_pypi


@pytest.mark.parametrize(
    "version",
    [
        "0.1.0a4",
        "0.9.0",
        "1.0.0a1",
        "1.0.0b1",
        "1.0.0rc1",
        "1.0.0.dev1",
    ],
)
def test_pre_1_or_prerelease_versions_are_not_publishable(version: str) -> None:
    assert not should_publish_to_pypi(version)


@pytest.mark.parametrize(
    "version",
    [
        "1.0.0",
        "1.0.1",
        "1.2.0",
        "2.0.0",
        "10.4.3",
    ],
)
def test_stable_versions_from_1_0_0_are_publishable(version: str) -> None:
    assert should_publish_to_pypi(version)


@pytest.mark.parametrize(
    "version",
    [
        "",
        "v1.0.0",
        "01.0.0",
        "1.00.0",
        "1.0",
        "1.0.0+local",
        "1.0.0.post1",
    ],
)
def test_noncanonical_stable_versions_are_not_publishable(version: str) -> None:
    assert not should_publish_to_pypi(version)
