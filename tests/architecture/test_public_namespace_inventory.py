"""V1-01.A executable inventory for every consumer-facing namespace."""

import pyschedulekit
import pyschedulekit.api as public_api
import pyschedulekit.experimental as experimental
import pyschedulekit.postgres as postgres
import pyschedulekit.testing as testing
from pyschedulekit.api._manifest import (
    EXPERIMENTAL_PUBLIC_NAMES,
    POSTGRES_PUBLIC_NAMES,
    PUBLIC_NAMESPACE_CLASSIFICATIONS,
    ROOT_METADATA_NAMES,
    STABLE_PUBLIC_NAMES,
    TESTING_PUBLIC_NAMES,
)


def test_v1_01a_namespace_classifications_are_exact() -> None:
    assert PUBLIC_NAMESPACE_CLASSIFICATIONS == {
        "pyschedulekit": "stable-candidate",
        "pyschedulekit.api": "stable-candidate",
        "pyschedulekit.postgres": "stable-candidate",
        "pyschedulekit.testing": "supported-testing",
        "pyschedulekit.experimental": "experimental",
    }


def test_v1_01a_inventory_counts_and_sets_are_stable() -> None:
    assert len(STABLE_PUBLIC_NAMES) == 104
    assert len(ROOT_METADATA_NAMES) == 1
    assert len(POSTGRES_PUBLIC_NAMES) == 2
    assert len(TESTING_PUBLIC_NAMES) == 5
    assert len(EXPERIMENTAL_PUBLIC_NAMES) == 11

    named_surfaces = (
        STABLE_PUBLIC_NAMES,
        ROOT_METADATA_NAMES,
        POSTGRES_PUBLIC_NAMES,
        TESTING_PUBLIC_NAMES,
        EXPERIMENTAL_PUBLIC_NAMES,
    )
    for names in named_surfaces:
        assert tuple(sorted(names)) == names
        assert len(names) == len(set(names))

    for index, names in enumerate(named_surfaces):
        for other in named_surfaces[index + 1 :]:
            assert set(names).isdisjoint(other)


def test_v1_01a_runtime_exports_match_the_inventory() -> None:
    assert public_api.__all__ == list(STABLE_PUBLIC_NAMES)
    assert pyschedulekit.__all__ == [*STABLE_PUBLIC_NAMES, *ROOT_METADATA_NAMES]
    assert postgres.__all__ == list(POSTGRES_PUBLIC_NAMES)
    assert testing.__all__ == list(TESTING_PUBLIC_NAMES)
    assert experimental.__all__ == list(EXPERIMENTAL_PUBLIC_NAMES)

    for name in STABLE_PUBLIC_NAMES:
        assert getattr(pyschedulekit, name) is getattr(public_api, name)

    for name in ROOT_METADATA_NAMES:
        assert hasattr(pyschedulekit, name)

    assert set(EXPERIMENTAL_PUBLIC_NAMES).isdisjoint(pyschedulekit.__all__)
