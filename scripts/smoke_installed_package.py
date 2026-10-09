"""Smoke-test an installed PyScheduleKit distribution outside the source tree."""

from __future__ import annotations

from importlib.metadata import version
from importlib.resources import files
from importlib.util import find_spec

import pyschedulekit
import pyschedulekit.api as public_api


def main() -> None:
    installed_version = version("pyschedulekit")
    assert installed_version == pyschedulekit.__version__
    assert installed_version == "0.1.0a4"

    assert pyschedulekit.Scheduler is public_api.Scheduler
    assert pyschedulekit.IntervalTrigger is public_api.IntervalTrigger
    assert "Scheduler" in pyschedulekit.__all__
    assert "ExecutionClaim" not in pyschedulekit.__all__
    assert "PostgresUnitOfWorkFactory" not in pyschedulekit.__all__
    assert not hasattr(pyschedulekit, "PostgresUnitOfWorkFactory")

    if find_spec("psycopg") is None:
        try:
            import pyschedulekit.postgres  # noqa: F401
        except pyschedulekit.PyScheduleKitConfigurationError as exc:
            assert "pyschedulekit[postgres]" in str(exc)
        else:
            raise AssertionError(
                "PostgreSQL optional namespace must fail clearly without the postgres extra."
            )

    typing_marker = files("pyschedulekit").joinpath("py.typed")
    assert typing_marker.is_file()

    scheduler = pyschedulekit.Scheduler()
    health = scheduler.health()
    assert health.healthy
    assert health.persistence_available

    print(f"Installed PyScheduleKit {installed_version} smoke test passed.")


if __name__ == "__main__":
    main()
