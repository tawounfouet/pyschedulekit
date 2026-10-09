"""End-to-end qualification for async Python targets through Scheduler."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from pyschedulekit import Duration, IntervalTrigger, Scheduler, TargetRef
from pyschedulekit.domain.time import Instant
from pyschedulekit.infrastructure.asyncio_executor import AsyncPythonTargetRegistry
from pyschedulekit.ports.executor import TargetResolutionError
from pyschedulekit.ports.persistence import DuplicateScheduleError
from pyschedulekit.testing import MutableClock


def _instant(minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, 10, minute, tzinfo=UTC))


def _trigger() -> IntervalTrigger:
    return IntervalTrigger(
        every=Duration.minutes(10),
        anchor=_instant(10),
    )


def test_scheduler_register_async_target_executes_through_run_pending() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    async def refresh() -> None:
        await asyncio.sleep(0)
        calls.append("refresh")

    target = scheduler.register_async_target("jobs:refresh", refresh)
    assert target == TargetRef.async_python("jobs:refresh")

    scheduler.add_schedule(
        id="async-schedule",
        target=target,
        trigger=_trigger(),
    )
    clock.advance(Duration.minutes(10))

    result = scheduler.run_pending()

    assert result.succeeded == 1
    assert calls == ["refresh"]


def test_scheduler_add_schedule_auto_detects_async_callable() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    async def refresh() -> None:
        calls.append("refresh")

    scheduler.add_schedule(
        id="auto-async",
        target=refresh,
        trigger=_trigger(),
    )
    clock.advance(Duration.minutes(10))

    result = scheduler.run_pending()

    assert result.succeeded == 1
    assert calls == ["refresh"]


def test_failed_schedule_commit_compensates_implicit_async_registration() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)

    scheduler.add_schedule(
        id="schedule-1",
        target=TargetRef.python("already-declared"),
        trigger=_trigger(),
    )

    async def candidate() -> None:
        return None

    for _ in range(2):
        with pytest.raises(DuplicateScheduleError):
            scheduler.add_schedule(
                id="schedule-1",
                target=candidate,
                trigger=_trigger(),
            )

        with pytest.raises(TargetResolutionError, match="not registered"):
            scheduler._async_registry.resolve("local:schedule-1")


def test_async_target_retry_uses_existing_retry_lifecycle() -> None:
    from pyschedulekit import FixedBackoff, RetryPolicy

    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    attempts = 0

    async def flaky() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary")

    scheduler.add_schedule(
        id="async-retry",
        target=flaky,
        trigger=_trigger(),
        retry=RetryPolicy(
            max_attempts=2,
            backoff=FixedBackoff(Duration.minutes(2)),
        ),
    )

    clock.advance(Duration.minutes(10))
    first = scheduler.run_pending()
    assert first.retry_scheduled == 1
    assert attempts == 1

    clock.advance(Duration.minutes(2))
    second = scheduler.run_pending()

    assert second.succeeded == 1
    assert attempts == 2
