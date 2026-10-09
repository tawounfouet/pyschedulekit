"""Stable optional PostgreSQL persistence surface.

Install with:

    pip install "pyschedulekit[postgres]"

The root :mod:`pyschedulekit` package intentionally does not import this module so the
base installation keeps zero runtime dependencies.
"""

from __future__ import annotations

from pyschedulekit.errors import PyScheduleKitConfigurationError
from pyschedulekit.ports.persistence import TransientPersistenceError

try:
    from pyschedulekit.infrastructure.postgres import (
        PostgresUnitOfWorkFactory as PostgresUnitOfWorkFactory,
    )
except ModuleNotFoundError as exc:
    if exc.name is not None and (
        exc.name == "psycopg" or exc.name.startswith("psycopg.")
    ):
        raise PyScheduleKitConfigurationError(
            "PostgreSQL persistence requires the optional dependency extra: "
            'pip install "pyschedulekit[postgres]".'
        ) from exc
    raise


__all__ = [
    "PostgresUnitOfWorkFactory",
    "TransientPersistenceError",
]
