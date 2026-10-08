"""REL-05 fitness tests for the TestPyPI Trusted Publishing workflow."""

from pathlib import Path

WORKFLOW = Path(".github/workflows/release-candidate.yml")
ACTION_SHA = "f0b2c5066dd5e752990bc69b0109e84563bc8db1"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_t_testpypi_001_publish_job_is_tag_only_and_oidc_scoped() -> None:
    workflow = _workflow_text()

    assert "publish-testpypi:" in workflow
    assert "github.event_name == 'push'" in workflow
    assert "startsWith(github.ref, 'refs/tags/v')" in workflow
    assert "name: testpypi" in workflow
    assert "id-token: write" in workflow
    assert "contents: read" in workflow


def test_t_testpypi_002_publish_uses_exact_retained_candidate_artifact() -> None:
    workflow = _workflow_text()

    assert "needs.qualify-release-candidate.outputs.release-tag" in workflow
    assert "Download qualified release candidate" in workflow
    assert "sha256sum --check release-candidate-sha256.txt" in workflow
    assert "packages-dir: release-candidate/dist/" in workflow

    publish_section = workflow.split("  publish-testpypi:", 1)[1].split(
        "  verify-testpypi:",
        1,
    )[0]
    assert "python -m build" not in publish_section


def test_t_testpypi_003_publish_action_is_sha_pinned_without_static_credentials() -> None:
    workflow = _workflow_text()
    publish_section = workflow.split("  publish-testpypi:", 1)[1].split(
        "  verify-testpypi:",
        1,
    )[0]

    assert f"pypa/gh-action-pypi-publish@{ACTION_SHA}" in publish_section
    assert "repository-url: https://test.pypi.org/legacy/" in publish_section
    assert "username:" not in publish_section
    assert "password:" not in publish_section
    assert "PYPI_TOKEN" not in publish_section
    assert "TEST_PYPI_TOKEN" not in publish_section


def test_t_testpypi_004_post_publish_verification_reads_from_testpypi() -> None:
    workflow = _workflow_text()
    verify_section = workflow.split("  verify-testpypi:", 1)[1]

    assert "--index-url https://test.pypi.org/simple/" in verify_section
    assert "--no-deps" in verify_section
    assert "needs.qualify-release-candidate.outputs.package-version" in verify_section
    assert 'cd /tmp' in verify_section
    assert "scripts/smoke_installed_package.py" in verify_section
