"""Regression tests for target-registry transaction safety."""

from datetime import UTC, datetime

import pytest

from pyschedulekit import CronTrigger, Duration, IntervalTrigger, Scheduler, TargetRef, Timezone
from pyschedulekit.domain.time import Instant
from pyschedulekit.infrastructure.local_executor import PythonTargetRegistry
from pyschedulekit.ports.executor import TargetResolutionError
from pyschedulekit.ports.persistence import DuplicateScheduleError
from pyschedulekit.testing import MutableClock


def _instant(minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, minute, tzinfo=UTC))


def test_failed_schedule_commit_compensates_implicit_target_registration() -> None:
    clock = MutableClock(_instant())
    registry = PythonTargetRegistry()
    scheduler = Scheduler(clock=clock, registry=registry)
    trigger = IntervalTrigger(
        every=Duration.minutes(10),
        anchor=_instant(10),
    )

    scheduler.add_schedule(
        id="schedule-1",
        target=TargetRef.python("already-declared"),
        trigger=trigger,
    )

    def candidate() -> None:
        return None

    for _ in range(2):
        with pytest.raises(DuplicateScheduleError):
            scheduler.add_schedule(
                id="schedule-1",
                target=candidate,
                trigger=trigger,
            )

        with pytest.raises(TargetResolutionError, match="not registered"):
            registry.resolve("local:schedule-1")


def test_precommit_validation_failure_compensates_implicit_target_registration() -> None:
    clock = MutableClock(_instant())
    registry = PythonTargetRegistry()
    scheduler = Scheduler(clock=clock, registry=registry)

    def candidate() -> None:
        return None

    with pytest.raises(ValueError, match="timezone must match"):
        scheduler.add_schedule(
            id="invalid-cron",
            target=candidate,
            trigger=CronTrigger(
                "0 9 * * *",
                timezone=Timezone("Europe/Paris"),
            ),
            timezone=Timezone("UTC"),
        )

    with pytest.raises(TargetResolutionError, match="not registered"):
        registry.resolve("local:invalid-cron")
