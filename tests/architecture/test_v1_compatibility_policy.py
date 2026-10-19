"""V1-01.F executable compatibility and deprecation policy."""

from pathlib import Path

from pyschedulekit.api._manifest import (
    V1_BREAKING_CHANGE_CLASSES,
    V1_DEPRECATION_POLICY,
    V1_PROTECTED_CONTRACT_ELEMENTS,
    V1_STABLE_COMPATIBILITY_POLICY,
)

POLICY_DOCUMENT = "V1-01F_COMPATIBILITY_DEPRECATION_POLICY.md"

POLICY_REFERENCES = (
    Path("AGENTS.md"),
    Path("docs/ARCHITECTURE.md"),
    Path("docs/SDLC.md"),
    Path("docs/api/README.md"),
    Path("docs/release/00_RELEASE_ENGINEERING_ROADMAP.md"),
    Path("docs/v1/README.md"),
)


def test_v1_01f_stable_compatibility_policy_is_exact() -> None:
    assert V1_STABLE_COMPATIBILITY_POLICY == {
        "additive-public-api": "minor-or-major",
        "breaking-public-change": "next-major-only",
        "compatible-bug-fix": "patch-minor-or-major",
        "persistence-floor": "frozen-for-major-after-v1-02",
        "public-typing": "previously-valid-consumer-typing-remains-valid",
        "stable-public-api": "semver-protected-within-major",
    }


def test_v1_01f_deprecation_policy_is_exact() -> None:
    assert V1_DEPRECATION_POLICY == {
        "changelog-required": True,
        "migration-guidance-required": True,
        "minimum-prior-stable-releases": 1,
        "removal-boundary": "next-major-only",
        "warning-category": "PyScheduleKitDeprecationWarning",
    }


def test_v1_01f_protected_contract_elements_are_exact() -> None:
    assert V1_PROTECTED_CONTRACT_ELEMENTS == (
        "callable-signatures",
        "documented-runtime-semantics",
        "enum-members-and-values",
        "exception-catch-categories",
        "protocol-members",
        "public-names",
        "public-result-fields",
        "public-typing-contracts",
        "stable-secondary-namespaces",
    )


def test_v1_01f_breaking_change_classes_are_explicit() -> None:
    assert V1_BREAKING_CHANGE_CLASSES == (
        "change-documented-runtime-meaning",
        "change-enum-value",
        "change-exception-catch-category",
        "invalidate-previously-valid-typing",
        "make-optional-parameter-required",
        "narrow-accepted-input-contract",
        "remove-or-rename-public-name",
        "remove-protocol-member",
        "remove-public-result-field",
        "rename-parameter",
        "restrict-parameter-calling-mode",
        "widen-return-contract-incompatibly",
    )


def test_v1_01f_canonical_policy_is_referenced_by_project_guidance() -> None:
    missing = [
        str(path)
        for path in POLICY_REFERENCES
        if POLICY_DOCUMENT not in path.read_text(encoding="utf-8")
    ]
    assert not missing, (
        "canonical compatibility policy must be referenced by project guidance: "
        + ", ".join(missing)
    )
