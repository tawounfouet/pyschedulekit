"""Inspect scheduler health and startup readiness."""

from datetime import UTC, datetime

from pyschedulekit import Instant, Scheduler
from pyschedulekit.testing import MutableClock


def main() -> None:
    clock = MutableClock(Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC)))
    scheduler = Scheduler(clock=clock)

    health = scheduler.health()
    before = scheduler.readiness()

    assert health.healthy
    assert health.persistence_available
    assert not before.ready
    assert not before.recovered
    assert not before.reconciled

    # The first scheduling cycle crosses crash-recovery and reconciliation barriers.
    scheduler.run_pending()
    after = scheduler.readiness()

    assert after.ready
    assert after.recovered
    assert after.reconciled
    print("operational health: scheduler is ready after startup barriers")


if __name__ == "__main__":
    main()
