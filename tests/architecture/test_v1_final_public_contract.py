"""V1-01.H final executable public-contract review."""

import pyschedulekit
import pyschedulekit.api as public_api
import pyschedulekit.experimental as experimental
import pyschedulekit.postgres as postgres
import pyschedulekit.testing as testing
from pyschedulekit.api._manifest import (
    API_ONLY_V1_PUBLIC_NAMES,
    EXPERIMENTAL_PUBLIC_NAMES,
    LEGACY_ROOT_NAMES,
    POSTGRES_PUBLIC_NAMES,
    PUBLIC_NAMESPACE_CLASSIFICATIONS,
    ROOT_METADATA_NAMES,
    ROOT_V1_PUBLIC_NAMES,
    STABLE_PUBLIC_NAMES,
    TESTING_PUBLIC_NAMES,
    V1_PUBLIC_CONTRACT_STATUS,
)


def test_v1_01h_primary_contract_is_final_and_exact() -> None:
    assert V1_PUBLIC_CONTRACT_STATUS == "frozen"
    assert len(ROOT_V1_PUBLIC_NAMES) == 63
    assert len(API_ONLY_V1_PUBLIC_NAMES) == 41
    assert len(STABLE_PUBLIC_NAMES) == 104

    assert tuple(sorted(ROOT_V1_PUBLIC_NAMES)) == ROOT_V1_PUBLIC_NAMES
    assert tuple(sorted(API_ONLY_V1_PUBLIC_NAMES)) == API_ONLY_V1_PUBLIC_NAMES
    assert set(ROOT_V1_PUBLIC_NAMES).isdisjoint(API_ONLY_V1_PUBLIC_NAMES)
    assert set(ROOT_V1_PUBLIC_NAMES) | set(API_ONLY_V1_PUBLIC_NAMES) == set(STABLE_PUBLIC_NAMES)


def test_v1_01h_runtime_root_is_the_compact_surface() -> None:
    assert public_api.__all__ == list(STABLE_PUBLIC_NAMES)
    assert pyschedulekit.__all__ == [*ROOT_V1_PUBLIC_NAMES, *ROOT_METADATA_NAMES]

    for name in ROOT_V1_PUBLIC_NAMES:
        assert getattr(pyschedulekit, name) is getattr(public_api, name)

    for name in API_ONLY_V1_PUBLIC_NAMES:
        assert hasattr(public_api, name)
        assert not hasattr(pyschedulekit, name)


def test_v1_01h_legacy_redirects_are_physically_removed() -> None:
    assert "__getattr__" not in vars(pyschedulekit)

    for name in LEGACY_ROOT_NAMES:
        assert name in EXPERIMENTAL_PUBLIC_NAMES
        assert not hasattr(pyschedulekit, name)
        assert hasattr(experimental, name)


def test_v1_01h_secondary_surfaces_remain_exact() -> None:
    assert postgres.__all__ == list(POSTGRES_PUBLIC_NAMES)
    assert testing.__all__ == list(TESTING_PUBLIC_NAMES)
    assert experimental.__all__ == list(EXPERIMENTAL_PUBLIC_NAMES)
    assert hasattr(pyschedulekit, "__version__")


def test_v1_01h_namespace_classifications_are_final() -> None:
    assert PUBLIC_NAMESPACE_CLASSIFICATIONS == {
        "pyschedulekit": "stable",
        "pyschedulekit.api": "stable",
        "pyschedulekit.postgres": "stable-optional",
        "pyschedulekit.testing": "stable-testing",
        "pyschedulekit.experimental": "experimental",
    }
