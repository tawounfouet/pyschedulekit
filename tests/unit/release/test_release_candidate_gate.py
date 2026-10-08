"""REL-04 tests for the release-candidate version gate."""

from pathlib import Path

import pytest

from scripts import verify_release_candidate as release_gate


def test_t_release_gate_001_accepts_canonical_v_prefixed_tag() -> None:
    assert release_gate.release_version_from_tag("v0.1.0a1") == "0.1.0a1"


@pytest.mark.parametrize(
    "release_tag",
    [
        "0.1.0a1",
        "v",
        " v0.1.0a1",
        "v0.1.0a1 ",
    ],
)
def test_t_release_gate_002_rejects_non_canonical_tags(release_tag: str) -> None:
    with pytest.raises(release_gate.ReleaseCandidateValidationError):
        release_gate.release_version_from_tag(release_tag)


def test_t_release_gate_003_rejects_tag_source_version_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    called = False

    def unexpected_distribution_validation(dist_dir: Path) -> tuple[Path, Path]:
        nonlocal called
        called = True
        return dist_dir / "wheel.whl", dist_dir / "source.tar.gz"

    monkeypatch.setattr(
        release_gate,
        "validate_distribution",
        unexpected_distribution_validation,
    )

    with pytest.raises(
        release_gate.ReleaseCandidateValidationError,
        match="does not match",
    ):
        release_gate.validate_release_candidate(
            release_tag="v0.1.0a2",
            dist_dir=tmp_path,
            package_version="0.1.0a1",
        )

    assert called is False


def test_t_release_gate_004_matching_tag_delegates_to_distribution_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    wheel = tmp_path / "pyschedulekit-0.1.0a1-py3-none-any.whl"
    sdist = tmp_path / "pyschedulekit-0.1.0a1.tar.gz"

    def qualified_distributions(dist_dir: Path) -> tuple[Path, Path]:
        assert dist_dir == tmp_path
        return wheel, sdist

    monkeypatch.setattr(
        release_gate,
        "validate_distribution",
        qualified_distributions,
    )

    assert release_gate.validate_release_candidate(
        release_tag="v0.1.0a1",
        dist_dir=tmp_path,
        package_version="0.1.0a1",
    ) == (wheel, sdist)
