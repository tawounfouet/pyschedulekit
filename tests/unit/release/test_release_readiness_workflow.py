"""REL-08 fitness tests for the manual release-readiness workflow."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github/workflows/release-readiness.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_t_release_readiness_001_workflow_is_manual_only() -> None:
    workflow = _workflow_text()

    assert "workflow_dispatch:" in workflow
    assert "push:" not in workflow
    assert "pull_request:" not in workflow


def test_t_release_readiness_002_requires_external_control_acknowledgements() -> None:
    workflow = _workflow_text()

    assert "testpypi_trusted_publisher_ready:" not in workflow
    assert "pypi_trusted_publisher_ready:" in workflow
    assert "immutable_releases_ready:" in workflow
    assert 'test "$PYPI_READY" = "true"' in workflow
    assert 'test "$IMMUTABLE_RELEASES_READY" = "true"' in workflow


def test_t_release_readiness_003_refuses_non_main_and_existing_tag() -> None:
    workflow = _workflow_text()

    assert "refs/heads/main" in workflow
    assert "git ls-remote --exit-code --tags origin" in workflow
    assert "Never reuse or move a release tag." in workflow


def test_t_release_readiness_004_rehearses_full_distribution_gate() -> None:
    workflow = _workflow_text()

    assert "python -m scripts.release_preflight" in workflow
    assert "python -m build" in workflow
    assert "python -m twine check --strict dist/*" in workflow
    assert "python -m scripts.verify_distribution dist" in workflow
    assert "python -m scripts.verify_release_candidate" in workflow


def test_t_release_readiness_005_workflow_never_creates_or_pushes_tag() -> None:
    workflow = _workflow_text()
    commands = [
        line.strip()
        for line in workflow.splitlines()
        if line.strip() and not line.strip().startswith("echo ")
    ]

    assert all(not line.startswith("git tag ") for line in commands)
    assert all(not line.startswith("git push ") for line in commands)
    assert "This workflow intentionally did not create or push a tag." in workflow


def test_t_release_readiness_006_defaults_to_next_unpublished_alpha_tag() -> None:
    workflow = _workflow_text()

    assert 'default: "v0.1.0a4"' in workflow
    assert 'default: "v0.1.0a3"' not in workflow

