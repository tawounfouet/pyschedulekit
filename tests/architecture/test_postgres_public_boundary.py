"""PG-05 public-boundary contract for optional PostgreSQL persistence."""

from __future__ import annotations

import pyschedulekit
import pyschedulekit.postgres as postgres_api
from pyschedulekit.api._manifest import STABLE_PUBLIC_NAMES
from pyschedulekit.infrastructure.postgres import (
    PostgresUnitOfWorkFactory as InternalPostgresUnitOfWorkFactory,
)
from pyschedulekit.ports.persistence import TransientPersistenceError


def test_postgres_factory_is_public_only_through_optional_namespace() -> None:
    assert "PostgresUnitOfWorkFactory" not in STABLE_PUBLIC_NAMES
    assert not hasattr(pyschedulekit, "PostgresUnitOfWorkFactory")

    assert (
        postgres_api.PostgresUnitOfWorkFactory
        is InternalPostgresUnitOfWorkFactory
    )
    assert postgres_api.__all__ == [
        "PostgresUnitOfWorkFactory",
        "TransientPersistenceError",
    ]


def test_postgres_transient_error_is_available_with_optional_adapter() -> None:
    assert postgres_api.TransientPersistenceError is TransientPersistenceError
