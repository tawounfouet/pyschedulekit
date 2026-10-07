"""LOT-30 end-to-end qualification for public Scheduler observability."""

from datetime import UTC, datetime

from pyschedulekit import Duration, IntervalTrigger, Scheduler
from pyschedulekit.domain.time import Instant
from pyschedulekit.infrastructure.observability import InMemoryObservationSink
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def test_t_observability_e2e_001_successful_cycle_emits_structured_observations() -> None:
    clock = MutableClock(_instant())
    sink = InMemoryObservationSink()
    scheduler = Scheduler(
        clock=clock,
        observation_sink=sink,
    )
    calls: list[str] = []

    scheduler.add_schedule(
        id="observed",
        target=lambda: calls.append("ran"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(minute=10),
        ),
    )

    clock.advance(Duration.minutes(10))
    result = scheduler.run_pending()

    assert calls == ["ran"]
    assert result.succeeded == 1

    attempts = sink.by_name("execution.attempt.completed")
    cycles = sink.by_name("scheduler.cycle.completed")

    assert len(attempts) == 1
    assert attempts[0].attribute("state") == "SUCCESS"
    assert attempts[0].attribute("succeeded") is True
    assert attempts[0].attribute("retry_scheduled") is False

    assert len(cycles) == 1
    assert cycles[0].attribute("materialized_requests") == 1
    assert cycles[0].attribute("executions") == 1
    assert cycles[0].attribute("succeeded") == 1
    assert cycles[0].attribute("failed") == 0
    assert cycles[0].attribute("errors") == 0


def test_t_observability_e2e_002_noop_cycle_is_still_observable() -> None:
    clock = MutableClock(_instant())
    sink = InMemoryObservationSink()
    scheduler = Scheduler(
        clock=clock,
        observation_sink=sink,
    )

    result = scheduler.run_pending()

    assert result.executions == ()
    cycles = sink.by_name("scheduler.cycle.completed")
    assert len(cycles) == 1
    assert cycles[0].attribute("materialized_requests") == 0
    assert cycles[0].attribute("executions") == 0
