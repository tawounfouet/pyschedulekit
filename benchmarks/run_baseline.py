"""Reproducible performance baselines for PyScheduleKit.

The harness reports measurements instead of treating one machine's wall-clock latency as a
universal product guarantee. Optional ratio guardrails catch catastrophic complexity drift.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from time import perf_counter_ns

from pyschedulekit import Duration, Instant, IntervalTrigger, Scheduler, TargetRef


@dataclass(frozen=True, slots=True)
class BenchmarkProfile:
    interval_iterations: int
    repeats: int
    schedule_counts: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class TimingSummary:
    median_ns: int
    minimum_ns: int
    maximum_ns: int


PROFILES = {
    "smoke": BenchmarkProfile(
        interval_iterations=2_000,
        repeats=3,
        schedule_counts=(100, 1_000),
    ),
    "ci": BenchmarkProfile(
        interval_iterations=20_000,
        repeats=5,
        schedule_counts=(1_000, 10_000),
    ),
    "full": BenchmarkProfile(
        interval_iterations=100_000,
        repeats=9,
        schedule_counts=(1_000, 10_000, 50_000),
    ),
}

INTERVAL_FAR_TO_NEAR_MAX_RATIO = 50.0
IDLE_10K_TO_1K_MAX_RATIO = 30.0


class BenchmarkClock:
    def __init__(self, current: Instant) -> None:
        self._current = current

    def now(self) -> Instant:
        return self._current


def _timed_batches(
    operation: Callable[[], None],
    *,
    iterations: int,
    repeats: int,
) -> TimingSummary:
    per_call: list[int] = []

    operation()
    for _ in range(repeats):
        started = perf_counter_ns()
        for _ in range(iterations):
            operation()
        elapsed = perf_counter_ns() - started
        per_call.append(max(1, elapsed // iterations))

    return TimingSummary(
        median_ns=int(median(per_call)),
        minimum_ns=min(per_call),
        maximum_ns=max(per_call),
    )


def _measure_interval(profile: BenchmarkProfile) -> dict[str, object]:
    anchor = Instant(datetime(2026, 1, 1, 0, 0, tzinfo=UTC))
    trigger = IntervalTrigger(
        every=Duration.minutes(1),
        anchor=anchor,
    )
    near_reference = anchor.add(Duration.days(1))
    far_reference = anchor.add(Duration.days(3650))

    near_expected = near_reference.add(Duration.minutes(1))
    far_expected = far_reference.add(Duration.minutes(1))
    assert trigger.next_after(near_reference) == near_expected
    assert trigger.next_after(far_reference) == far_expected

    near = _timed_batches(
        lambda: trigger.next_after(near_reference),
        iterations=profile.interval_iterations,
        repeats=profile.repeats,
    )
    far = _timed_batches(
        lambda: trigger.next_after(far_reference),
        iterations=profile.interval_iterations,
        repeats=profile.repeats,
    )
    ratio = far.median_ns / near.median_ns

    return {
        "iterations_per_repeat": profile.interval_iterations,
        "near": asdict(near),
        "far": asdict(far),
        "far_to_near_ratio": ratio,
    }


def _measure_idle_cycle(
    *,
    schedule_count: int,
    repeats: int,
) -> dict[str, object]:
    start = Instant(datetime(2026, 1, 1, 0, 0, tzinfo=UTC))
    clock = BenchmarkClock(start)
    scheduler = Scheduler(clock=clock, worker_id=f"bench-{schedule_count}")
    target = TargetRef.python("benchmark:no-op")
    trigger = IntervalTrigger(
        every=Duration.minutes(1),
        anchor=start.add(Duration.days(1)),
    )

    setup_started = perf_counter_ns()
    for index in range(schedule_count):
        scheduler.add_schedule(
            id=f"benchmark-{schedule_count}-{index:05d}",
            target=target,
            trigger=trigger,
        )
    setup_ns = perf_counter_ns() - setup_started

    # Cross recovery/reconciliation barriers before timing steady-state selection.
    warmup = scheduler.run_pending()
    assert warmup.executions == ()
    assert warmup.materialized_request_ids == ()

    durations: list[int] = []
    for _ in range(repeats):
        started = perf_counter_ns()
        result = scheduler.run_pending()
        elapsed = perf_counter_ns() - started
        assert result.executions == ()
        assert result.materialized_request_ids == ()
        durations.append(max(1, elapsed))

    summary = TimingSummary(
        median_ns=int(median(durations)),
        minimum_ns=min(durations),
        maximum_ns=max(durations),
    )
    return {
        "schedule_count": schedule_count,
        "setup_ns": setup_ns,
        "idle_cycle": asdict(summary),
    }


def run_baseline(profile_name: str) -> dict[str, object]:
    profile = PROFILES[profile_name]
    interval = _measure_interval(profile)
    scheduler_results = {
        str(count): _measure_idle_cycle(
            schedule_count=count,
            repeats=profile.repeats,
        )
        for count in profile.schedule_counts
    }

    scaling_ratio: float | None = None
    if "1000" in scheduler_results and "10000" in scheduler_results:
        one_k = scheduler_results["1000"]["idle_cycle"]
        ten_k = scheduler_results["10000"]["idle_cycle"]
        assert isinstance(one_k, dict)
        assert isinstance(ten_k, dict)
        scaling_ratio = int(ten_k["median_ns"]) / int(one_k["median_ns"])

    return {
        "schema_version": 1,
        "profile": profile_name,
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "interval_next_after": interval,
        "idle_scheduler_cycle": {
            "results": scheduler_results,
            "ten_k_to_one_k_ratio": scaling_ratio,
        },
    }


def assert_guardrails(results: dict[str, object]) -> None:
    interval = results["interval_next_after"]
    idle = results["idle_scheduler_cycle"]
    assert isinstance(interval, dict)
    assert isinstance(idle, dict)

    interval_ratio = float(interval["far_to_near_ratio"])
    if interval_ratio > INTERVAL_FAR_TO_NEAR_MAX_RATIO:
        raise AssertionError(
            "IntervalTrigger near/far ratio exceeded guardrail: "
            f"{interval_ratio:.2f} > {INTERVAL_FAR_TO_NEAR_MAX_RATIO:.2f}"
        )

    idle_ratio = idle["ten_k_to_one_k_ratio"]
    if idle_ratio is not None and float(idle_ratio) > IDLE_10K_TO_1K_MAX_RATIO:
        raise AssertionError(
            "10k/1k idle-cycle ratio exceeded guardrail: "
            f"{float(idle_ratio):.2f} > {IDLE_10K_TO_1K_MAX_RATIO:.2f}"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILES),
        default="smoke",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--assert-guardrails", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    results = run_baseline(args.profile)

    if args.assert_guardrails:
        assert_guardrails(results)

    rendered = json.dumps(results, indent=2, sort_keys=True)
    print(rendered)

    if args.output is not None:
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
