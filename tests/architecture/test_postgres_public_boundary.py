"""PG-01 architecture boundary: incomplete PostgreSQL adapter stays internal."""

from __future__ import annotations

import pyschedulekit
from pyschedulekit.api._manifest import STABLE_PUBLIC_NAMES


def test_pg01_postgres_core_factory_is_not_stable_public_api() -> None:
    assert "PostgresCoreUnitOfWorkFactory" not in STABLE_PUBLIC_NAMES
    assert "PostgresUnitOfWorkFactory" not in STABLE_PUBLIC_NAMES
    assert not hasattr(pyschedulekit, "PostgresCoreUnitOfWorkFactory")
    assert not hasattr(pyschedulekit, "PostgresUnitOfWorkFactory")
