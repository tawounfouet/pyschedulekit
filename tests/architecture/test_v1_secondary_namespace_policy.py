"""V1-01.C compatibility policy for secondary public namespaces."""

from pyschedulekit.api._manifest import (
    EXPERIMENTAL_PUBLIC_NAMES,
    LEGACY_ROOT_REDIRECT_V1_POLICY,
    POSTGRES_PUBLIC_NAMES,
    ROOT_METADATA_NAMES,
    ROOT_METADATA_V1_POLICY,
    SECONDARY_NAMESPACE_V1_POLICIES,
    TESTING_PUBLIC_NAMES,
    UNLISTED_SUBMODULE_V1_POLICY,
)


def test_v1_01c_secondary_namespace_policies_are_exact() -> None:
    assert SECONDARY_NAMESPACE_V1_POLICIES == {
        "pyschedulekit.experimental": "experimental-no-semver",
        "pyschedulekit.postgres": "stable-optional",
        "pyschedulekit.testing": "stable-testing",
    }

    assert ROOT_METADATA_V1_POLICY == "stable-presence"
    assert LEGACY_ROOT_REDIRECT_V1_POLICY == "remove-before-v1.0.0"
    assert UNLISTED_SUBMODULE_V1_POLICY == "internal-no-compatibility"


def test_v1_01c_policy_surfaces_have_exact_inventory() -> None:
    assert POSTGRES_PUBLIC_NAMES == (
        "PostgresUnitOfWorkFactory",
        "TransientPersistenceError",
    )
    assert TESTING_PUBLIC_NAMES == (
        "FixedClock",
        "MutableClock",
        "TriggerContractSuite",
        "TriggerContractViolation",
        "add_request_with_parent",
    )
    assert ROOT_METADATA_NAMES == ("__version__",)
    assert len(EXPERIMENTAL_PUBLIC_NAMES) == 11
