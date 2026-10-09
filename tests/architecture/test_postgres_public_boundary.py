"""PG-05 public-boundary contract for optional PostgreSQL persistence."""

from __future__ import annotations

from pathlib import Path

import pyschedulekit
import pyschedulekit.postgres as postgres_api
from pyschedulekit.api._manifest import STABLE_PUBLIC_NAMES
from pyschedulekit.infrastructure.postgres import (
    PostgresUnitOfWorkFactory as InternalPostgresUnitOfWorkFactory,
)
from pyschedulekit.ports.persistence import TransientPersistenceError

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DOC = REPO_ROOT / "docs" / "api" / "README.md"
SUPPORT_DOC = REPO_ROOT / "docs" / "postgres" / "SUPPORT_AND_MIGRATION.md"


def test_postgres_factory_is_public_only_through_optional_namespace() -> None:
    assert "PostgresUnitOfWorkFactory" not in STABLE_PUBLIC_NAMES
    assert not hasattr(pyschedulekit, "PostgresUnitOfWorkFactory")

    assert postgres_api.PostgresUnitOfWorkFactory is InternalPostgresUnitOfWorkFactory
    assert postgres_api.__all__ == [
        "PostgresUnitOfWorkFactory",
        "TransientPersistenceError",
    ]


def test_postgres_transient_error_is_available_with_optional_adapter() -> None:
    assert postgres_api.TransientPersistenceError is TransientPersistenceError


def test_optional_postgres_public_surface_is_documented() -> None:
    api_text = API_DOC.read_text(encoding="utf-8")
    support_text = SUPPORT_DOC.read_text(encoding="utf-8")

    assert "`PostgresUnitOfWorkFactory`" in api_text
    assert "`TransientPersistenceError`" in api_text
    assert "pyschedulekit.postgres" in api_text

    assert "| 16 | ✅ supported / CI-qualified |" in support_text
    assert "| 17 | ✅ supported / CI-qualified |" in support_text
    assert "| 18 | ✅ supported / CI-qualified |" in support_text
    assert "SCHEMA_VERSION = 1" in support_text
    assert "SQLite → PostgreSQL" in support_text
