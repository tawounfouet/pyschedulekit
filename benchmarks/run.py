"""Reproducible PyScheduleKit micro/macro benchmark harness."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter

import pyschedulekit
from pyschedulekit import (
    CronTrigger,
    Duration,
    Instant,
    IntervalTrigger,
    Scheduler,
    SqliteUnitOfWorkFactory,
    TargetRef,
    Timezone,
)
from pyschedulekit.testing import MutableClock


@dataclass(frozen=True, slots=True)
class BenchmarkProfile:
    repeats: int
    interval_iterations: int
    cron_iterations: int
    memory_schedules: int
    sqlite_schedules: int
    postgres_schedules: int
    memory_idle_counts: tuple[int, int]


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    name: str
    operations: int
    repeats: int
    median_seconds: float
    min_seconds: float
    max_seconds: float
    operations_per_second: float


PROFILES = {
    "smoke": BenchmarkProfile(
        repeats=2,
        interval_iterations=200,
        cron_iterations=40,
        memory_schedules=5,
        sqlite_schedules=3,
        postgres_schedules=3,
        memory_idle_counts=(100, 1_000),
    ),
    "standard": BenchmarkProfile(
        repeats=7,
        interval_iterations=100_000,
        cron_iterations=2_000,
        memory_schedules=250,
        sqlite_schedules=50,
        postgres_schedules=50,
        memory_idle_counts=(1_000, 10_000),
    ),
}


def _result_from_samples(
    *,
    name: str,
    operations: int,
    repeats: int,
    samples: list[float],
) -> BenchmarkResult:
    middle = median(samples)
    return BenchmarkResult(
        name=name,
        operations=operations,
        repeats=repeats,
        median_seconds=middle,
        min_seconds=min(samples),
        max_seconds=max(samples),
        operations_per_second=operations / middle if middle > 0 else float("inf"),
    )


def _measure(
    *,
    name: str,
    operations: int,
    repeats: int,
    sample: Callable[[], float],
) -> BenchmarkResult:
    return _result_from_samples(
        name=name,
        operations=operations,
        repeats=repeats,
        samples=[sample() for _ in range(repeats)],
    )


def _interval_sample(iterations: int) -> float:
    reference = Instant(datetime(2026, 1, 1, tzinfo=UTC))
    trigger = IntervalTrigger(
        every=Duration.seconds(30),
        anchor=reference.add(Duration.seconds(30)),
    )

    started = perf_counter()
    current = reference
    for _ in range(iterations):
        occurrence = trigger.next_after(current)
        assert occurrence is not None
        current = occurrence
    return perf_counter() - started


def _cron_sample(iterations: int) -> float:
    reference = Instant(datetime(2026, 1, 5, 7, 59, tzinfo=UTC))
    trigger = CronTrigger(
        "0 9 * * 1-5",
        timezone=Timezone("Europe/Paris"),
    )

    started = perf_counter()
    current = reference
    for _ in range(iterations):
        occurrence = trigger.next_after(current)
        assert occurrence is not None
        current = occurrence
    return perf_counter() - started


def _memory_cycle_sample(schedule_count: int) -> float:
    start = Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    clock = MutableClock(start)
    scheduler = Scheduler(clock=clock)

    for index in range(schedule_count):
        scheduler.add_schedule(
            id=f"memory-{index:05d}",
            target=lambda: None,
            trigger=IntervalTrigger(
                every=Duration.hours(1),
                anchor=start.add(Duration.minutes(1)),
            ),
        )

    clock.advance(Duration.minutes(1))
    started = perf_counter()
    result = scheduler.run_pending(limit=schedule_count)
    elapsed = perf_counter() - started

    assert result.succeeded == schedule_count
    return elapsed


def _sqlite_cycle_sample(schedule_count: int) -> float:
    start = Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))

    with TemporaryDirectory() as directory:
        database = Path(directory) / "benchmark.db"
        clock = MutableClock(start)
        scheduler = Scheduler(
            clock=clock,
            uow_factory=SqliteUnitOfWorkFactory(database),
            worker_id="benchmark-worker",
        )

        for index in range(schedule_count):
            scheduler.add_schedule(
                id=f"sqlite-{index:05d}",
                target=lambda: None,
                trigger=IntervalTrigger(
                    every=Duration.hours(1),
                    anchor=start.add(Duration.minutes(1)),
                ),
            )

        clock.advance(Duration.minutes(1))
        started = perf_counter()
        result = scheduler.run_pending(limit=schedule_count)
        elapsed = perf_counter() - started

        assert result.succeeded == schedule_count
        return elapsed


def _postgres_cycle_sample(schedule_count: int, dsn: str) -> float:
    # PostgreSQL is optional for the base package, so imports stay lazy.
    import psycopg

    from pyschedulekit.infrastructure.postgres import PostgresUnitOfWorkFactory

    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")

    start = Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    clock = MutableClock(start)
    scheduler = Scheduler(
        clock=clock,
        uow_factory=PostgresUnitOfWorkFactory(dsn),
        worker_id="benchmark-worker",
    )

    for index in range(schedule_count):
        scheduler.add_schedule(
            id=f"postgres-{index:05d}",
            target=lambda: None,
            trigger=IntervalTrigger(
                every=Duration.hours(1),
                anchor=start.add(Duration.minutes(1)),
            ),
        )

    clock.advance(Duration.minutes(1))
    started = perf_counter()
    result = scheduler.run_pending(limit=schedule_count)
    elapsed = perf_counter() - started

    assert result.succeeded == schedule_count
    return elapsed


def _memory_idle_result(
    *,
    schedule_count: int,
    repeats: int,
) -> BenchmarkResult:
    start = Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    clock = MutableClock(start)
    scheduler = Scheduler(
        clock=clock,
        worker_id=f"idle-benchmark-{schedule_count}",
    )
    target = TargetRef.python("benchmark:not-due")
    trigger = IntervalTrigger(
        every=Duration.minutes(1),
        anchor=start.add(Duration.days(1)),
    )

    for index in range(schedule_count):
        scheduler.add_schedule(
            id=f"idle-{schedule_count}-{index:05d}",
            target=target,
            trigger=trigger,
        )

    warmup = scheduler.run_pending()
    assert warmup.executions == ()
    assert warmup.materialized_request_ids == ()

    samples: list[float] = []
    for _ in range(repeats):
        started = perf_counter()
        result = scheduler.run_pending()
        samples.append(perf_counter() - started)
        assert result.executions == ()
        assert result.materialized_request_ids == ()

    return _result_from_samples(
        name=f"run_pending_memory_idle_{schedule_count}",
        operations=schedule_count,
        repeats=repeats,
        samples=samples,
    )


def run(profile_name: str) -> dict[str, object]:
    profile = PROFILES[profile_name]
    sqlite_result = _measure(
        name="run_pending_sqlite",
        operations=profile.sqlite_schedules,
        repeats=profile.repeats,
        sample=lambda: _sqlite_cycle_sample(profile.sqlite_schedules),
    )
    results = [
        _measure(
            name="interval_next_after",
            operations=profile.interval_iterations,
            repeats=profile.repeats,
            sample=lambda: _interval_sample(profile.interval_iterations),
        ),
        _measure(
            name="cron_next_after",
            operations=profile.cron_iterations,
            repeats=profile.repeats,
            sample=lambda: _cron_sample(profile.cron_iterations),
        ),
        _measure(
            name="run_pending_memory",
            operations=profile.memory_schedules,
            repeats=profile.repeats,
            sample=lambda: _memory_cycle_sample(profile.memory_schedules),
        ),
        sqlite_result,
    ]

    postgres_dsn = os.getenv("PYSCHEDULEKIT_BENCHMARK_POSTGRES_DSN")
    postgres_result: BenchmarkResult | None = None
    if postgres_dsn:
        postgres_result = _measure(
            name="run_pending_postgres",
            operations=profile.postgres_schedules,
            repeats=profile.repeats,
            sample=lambda: _postgres_cycle_sample(
                profile.postgres_schedules,
                postgres_dsn,
            ),
        )
        results.append(postgres_result)

    small_count, large_count = profile.memory_idle_counts
    small_idle = _memory_idle_result(
        schedule_count=small_count,
        repeats=profile.repeats,
    )
    large_idle = _memory_idle_result(
        schedule_count=large_count,
        repeats=profile.repeats,
    )
    results.extend((small_idle, large_idle))

    return {
        "schema_version": 2,
        "profile": profile_name,
        "pyschedulekit_version": pyschedulekit.__version__,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "scaling": {
            "memory_idle_small_count": small_count,
            "memory_idle_large_count": large_count,
            "memory_idle_large_to_small_ratio": (
                large_idle.median_seconds / small_idle.median_seconds
                if small_idle.median_seconds > 0
                else float("inf")
            ),
            "postgres_to_sqlite_cycle_ratio": (
                postgres_result.median_seconds / sqlite_result.median_seconds
                if postgres_result is not None and sqlite_result.median_seconds > 0
                else None
            ),
        },
        "results": [asdict(result) for result in results],
    }


def render_markdown(report: dict[str, object]) -> str:
    rows = [
        "# PyScheduleKit Benchmark Report",
        "",
        f"- Profile: `{report['profile']}`",
        f"- PyScheduleKit: `{report['pyschedulekit_version']}`",
        f"- Python: `{report['python_implementation']} {report['python_version']}`",
        f"- Platform: `{report['platform']}`",
        "",
        "| Benchmark | Operations | Repeats | Median (s) | Min (s) | Max (s) | Ops/s |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for result in report["results"]:
        assert isinstance(result, dict)
        rows.append(
            "| {name} | {operations} | {repeats} | {median_seconds:.6f} | "
            "{min_seconds:.6f} | {max_seconds:.6f} | {operations_per_second:.2f} |".format(**result)
        )

    scaling = report["scaling"]
    assert isinstance(scaling, dict)
    rows.extend(
        [
            "",
            "## Scale evidence",
            "",
            (
                "- Idle in-memory cycle ratio "
                f"({scaling['memory_idle_large_count']}/"
                f"{scaling['memory_idle_small_count']} schedules): "
                f"`{float(scaling['memory_idle_large_to_small_ratio']):.2f}x`"
            ),
            *(
                [
                    (
                        "- PostgreSQL / SQLite due-cycle median ratio: "
                        f"`{float(scaling['postgres_to_sqlite_cycle_ratio']):.2f}x`"
                    )
                ]
                if scaling.get("postgres_to_sqlite_cycle_ratio") is not None
                else []
            ),
            "",
            "> Benchmark numbers are evidence, not CI pass/fail thresholds. Compare runs only",
            "> when Python version, platform, profile and workload remain comparable.",
            "",
        ]
    )
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=tuple(PROFILES), default="standard")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()

    report = run(args.profile)
    markdown = render_markdown(report)

    if args.json_out is not None:
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.markdown_out is not None:
        args.markdown_out.write_text(markdown, encoding="utf-8")

    sys.stdout.write(markdown)


if __name__ == "__main__":
    main()
