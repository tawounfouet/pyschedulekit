"""LOT-30 unit tests for dependency-neutral observability."""

from datetime import UTC, datetime

import pytest

from pyschedulekit.application.observability import Observer
from pyschedulekit.domain.time import Instant
from pyschedulekit.infrastructure.observability import InMemoryObservationSink
from pyschedulekit.ports.observability import Observation


def _instant() -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))


def test_t_observability_unit_001_observation_attributes_are_deterministic() -> None:
    observation = Observation.from_mapping(
        name="scheduler.cycle.completed",
        recorded_at=_instant(),
        attributes={
            "succeeded": 2,
            "failed": 1,
        },
    )

    assert observation.attributes == (
        ("failed", 1),
        ("succeeded", 2),
    )
    assert observation.attribute("succeeded") == 2


def test_t_observability_unit_002_rejects_invalid_observation_name() -> None:
    with pytest.raises(ValueError, match="name"):
        Observation(
            name=" ",
            recorded_at=_instant(),
        )


def test_t_observability_unit_003_in_memory_sink_is_queryable() -> None:
    sink = InMemoryObservationSink()
    observer = Observer(sink)

    observer.record(
        name="runtime.cycle.completed",
        recorded_at=_instant(),
        cycle_number=1,
    )
    observer.record(
        name="runtime.cycle.completed",
        recorded_at=_instant(),
        cycle_number=2,
    )

    assert sink.count("runtime.cycle.completed") == 2
    assert tuple(
        observation.attribute("cycle_number")
        for observation in sink.by_name("runtime.cycle.completed")
    ) == (1, 2)


def test_t_observability_unit_004_sink_failure_never_breaks_scheduler_path() -> None:
    class BrokenSink:
        def record(self, observation: Observation) -> None:
            del observation
            raise RuntimeError("telemetry backend unavailable")

    observer = Observer(BrokenSink())

    observer.record(
        name="scheduler.cycle.completed",
        recorded_at=_instant(),
        succeeded=1,
    )
