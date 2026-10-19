"""Seed and verify the V1-02.F PostgreSQL backup/restore rehearsal."""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime

from pyschedulekit import Duration, Instant, IntervalTrigger
from pyschedulekit.domain.schedule import Schedule, ScheduleDefinition, ScheduleId, TargetRef
from pyschedulekit.postgres import PostgresUnitOfWorkFactory

PROBE_ID = ScheduleId("v1-02f-backup-restore-probe")


def _instant(*, hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def _factory() -> PostgresUnitOfWorkFactory:
    dsn = os.environ["PYSCHEDULEKIT_TEST_POSTGRES_DSN"]
    return PostgresUnitOfWorkFactory(dsn)


def seed() -> None:
    schedule = Schedule.create(
        schedule_id=PROBE_ID,
        definition=ScheduleDefinition(
            target=TargetRef.python("jobs:v1-02f-backup-restore-probe"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(minute=10),
            ),
        ),
        reference=_instant(hour=9),
    )

    factory = _factory()
    with factory() as uow:
        if uow.schedules.get(PROBE_ID) is None:
            uow.schedules.add(schedule)
            uow.commit()

    verify()


def verify() -> None:
    factory = _factory()
    with factory() as uow:
        schedule = uow.schedules.get(PROBE_ID)

    if schedule is None:
        raise RuntimeError("PostgreSQL backup/restore probe Schedule is missing.")
    if schedule.definition.target != TargetRef.python("jobs:v1-02f-backup-restore-probe"):
        raise RuntimeError("PostgreSQL backup/restore probe target changed.")
    if schedule.next_run_time != _instant(minute=10):
        raise RuntimeError("PostgreSQL backup/restore probe next_run_time changed.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("seed", "verify"))
    args = parser.parse_args()

    if args.action == "seed":
        seed()
    else:
        verify()


if __name__ == "__main__":
    main()
