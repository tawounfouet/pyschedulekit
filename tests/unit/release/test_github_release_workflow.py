"""REL-07 fitness tests for GitHub Release and provenance workflow."""

from pathlib import Path

WORKFLOW = Path(".github/workflows/release-candidate.yml")
ATTEST_ACTION_SHA = "1e69f48acb82d1966a394da916b4c1698aa569d6"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_t_github_release_001_tagged_candidate_generates_build_provenance() -> None:
    workflow = _workflow_text()
    qualify_section = workflow.split("  qualify-release-candidate:", 1)[1].split(
        "  publish-testpypi:",
        1,
    )[0]

    assert "id-token: write" in qualify_section
    assert "attestations: write" in qualify_section
    assert "artifact-metadata: write" in qualify_section
    assert f"actions/attest@{ATTEST_ACTION_SHA}" in qualify_section
    assert "subject-checksums: release-candidate-sha256.txt" in qualify_section
    assert "github.event_name == 'push'" in qualify_section
    assert "startsWith(github.ref, 'refs/tags/v')" in qualify_section


def test_t_github_release_002_release_requires_verified_pypi_and_exact_artifacts() -> None:
    workflow = _workflow_text()
    release_section = workflow.split("  create-github-release:", 1)[1].split(
        "  verify-github-release:",
        1,
    )[0]

    assert "verify-pypi" in release_section
    assert "qualify-release-candidate" in release_section
    assert "contents: write" in release_section
    assert "release-candidate-dists-" in release_section
    assert "sha256sum --check release-candidate-sha256.txt" in release_section
    assert "python -m build" not in release_section


def test_t_github_release_003_release_uses_existing_tag_and_prerelease_semantics() -> None:
    workflow = _workflow_text()
    release_section = workflow.split("  create-github-release:", 1)[1].split(
        "  verify-github-release:",
        1,
    )[0]

    assert 'gh release create "$RELEASE_TAG"' in release_section
    assert "--verify-tag" in release_section
    assert "--generate-notes" in release_section
    assert "--prerelease" in release_section
    assert "--latest=false" in release_section
    assert "release-candidate/dist/*" in release_section
    assert "release-candidate/release-candidate-sha256.txt" in release_section


def test_t_github_release_004_release_assets_are_reverified_after_publication() -> None:
    workflow = _workflow_text()
    verify_section = workflow.split("  verify-github-release:", 1)[1]

    assert "gh release view" in verify_section
    assert "isDraft" in verify_section
    assert "isPrerelease" in verify_section
    assert "gh release download" in verify_section
    assert "release-assets/dist" in verify_section
    assert "release-candidate-sha256.txt" in verify_section
    assert "sha256sum --check release-candidate-sha256.txt" in verify_section


def test_t_github_release_005_build_provenance_is_verified_before_and_after_release() -> None:
    workflow = _workflow_text()

    create_section = workflow.split("  create-github-release:", 1)[1].split(
        "  verify-github-release:",
        1,
    )[0]
    verify_section = workflow.split("  verify-github-release:", 1)[1]

    assert 'gh attestation verify "$artifact" --repo "$GITHUB_REPOSITORY"' in create_section
    assert 'gh attestation verify "$artifact" --repo "$GITHUB_REPOSITORY"' in verify_section
