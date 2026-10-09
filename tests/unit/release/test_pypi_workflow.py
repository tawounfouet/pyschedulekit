"""REL-06 fitness tests for the production PyPI Trusted Publishing workflow."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github/workflows/release-candidate.yml"
ACTION_SHA = "dc37677b2e1c63e2034f94d8a5b11f265b73ba33"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_t_pypi_001_publish_job_requires_successful_qualification() -> None:
    workflow = _workflow_text()
    publish_section = workflow.split("  publish-pypi:", 1)[1].split(
        "  verify-pypi:",
        1,
    )[0]

    assert "qualify-release-candidate" in publish_section
    assert "github.event_name == 'push'" in publish_section
    assert "startsWith(github.ref, 'refs/tags/v')" in publish_section
    assert (
        "needs.qualify-release-candidate.outputs.public-pypi-eligible == 'true'" in publish_section
    )


def test_t_pypi_002_publish_job_uses_production_environment_and_oidc() -> None:
    workflow = _workflow_text()
    publish_section = workflow.split("  publish-pypi:", 1)[1].split(
        "  verify-pypi:",
        1,
    )[0]

    assert "name: pypi" in publish_section
    assert "url: https://pypi.org/p/pyschedulekit" in publish_section
    assert "id-token: write" in publish_section
    assert "contents: read" in publish_section


def test_t_pypi_003_publish_reuses_exact_candidate_without_rebuild() -> None:
    workflow = _workflow_text()
    publish_section = workflow.split("  publish-pypi:", 1)[1].split(
        "  verify-pypi:",
        1,
    )[0]

    assert "release-candidate-dists-" in publish_section
    assert "sha256sum --check release-candidate-sha256.txt" in publish_section
    assert "packages-dir: release-candidate/dist/" in publish_section
    assert "python -m build" not in publish_section


def test_t_pypi_004_official_action_is_sha_pinned_without_static_credentials() -> None:
    workflow = _workflow_text()
    publish_section = workflow.split("  publish-pypi:", 1)[1].split(
        "  verify-pypi:",
        1,
    )[0]

    assert f"pypa/gh-action-pypi-publish@{ACTION_SHA}" in publish_section
    assert "attestations: true" in publish_section
    assert "repository-url:" not in publish_section
    assert "username:" not in publish_section
    assert "password:" not in publish_section
    assert "PYPI_TOKEN" not in publish_section


def test_t_pypi_005_post_publish_verification_reads_from_pypi() -> None:
    workflow = _workflow_text()
    verify_section = workflow.split("  verify-pypi:", 1)[1]

    assert "--index-url https://pypi.org/simple/" in verify_section
    assert "--no-deps" in verify_section
    assert "needs.qualify-release-candidate.outputs.package-version" in verify_section
    assert "cd /tmp" in verify_section
    assert "scripts/smoke_installed_package.py" in verify_section


def test_t_pypi_006_qualification_exposes_publication_policy_output() -> None:
    workflow = _workflow_text()
    qualify_section = workflow.split("  qualify-release-candidate:", 1)[1].split(
        "  publish-pypi:",
        1,
    )[0]

    assert "public-pypi-eligible: ${{ steps.publication-policy.outputs.value }}" in qualify_section
    assert "python -m scripts.release_policy" in qualify_section
    assert 'echo "value=$value" >> "$GITHUB_OUTPUT"' in qualify_section
