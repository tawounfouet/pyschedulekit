# POST-05 — Performance Benchmarks

POST-05 introduces one reproducible benchmark surface:
`benchmarks/run.py`.

It combines representative trigger/runtime measurements with scale evidence for idle
in-memory scheduling. It does not define an absolute latency SLA.

## Goals

The benchmark layer answers five questions:

1. how fast are deterministic interval lookups?
2. how expensive are calendar/cron lookups?
3. how does one due-work cycle behave with many in-memory schedules?
4. how does the same cycle behave with durable SQLite persistence?
5. what is the direct lookup cost of a two-child temporal union?

It does **not** promise a performance SLA yet.

## Harness

Run:

```bash
python benchmarks/run.py --profile smoke
python benchmarks/run.py --profile standard
```

Persist evidence:

```bash
python benchmarks/run.py \
  --profile standard \
  --json-out benchmark-results.json \
  --markdown-out benchmark-results.md
```

The JSON report is machine-readable. The Markdown report is intended for human review and
GitHub Actions summaries.

## Profiles

### smoke

Used by the normal test suite only to prove the benchmark harness remains executable.

```text
repeats               2
interval iterations   200
AnyOf iterations      200
cron iterations       40
memory schedules      5
SQLite schedules      3
```

These numbers are deliberately too small to be treated as useful performance evidence.

### standard

The default evidence workload, automatically recorded after benchmark-relevant merges to
`main` and also available manually.

```text
repeats               7
interval iterations   100,000
AnyOf iterations      100,000
cron iterations       2,000
memory schedules      250
SQLite schedules      50
idle scale            1,000 → 10,000 schedules
```

Each benchmark reports median, min, max and operations/second. The report also includes the
idle in-memory large/small schedule-count scaling ratio.

## Benchmarks

### interval_next_after

Measures only repeated `IntervalTrigger.next_after()` calls after trigger construction.

This is primarily an algorithmic guard: interval lookup should remain direct arithmetic and
must not replay the schedule history.

### cron_next_after

Measures repeated `CronTrigger.next_after()` calls for the weekday Paris expression:

```text
0 9 * * 1-5
```

This covers civil-calendar iteration, weekday matching and timezone conversion.

### any_of_next_after

Measures repeated `AnyOfTrigger.next_after()` calls over two anchored interval children
with overlapping occurrence streams. Construction happens before timing. The measurement
therefore captures child lookup, earliest-candidate selection and duplicate-free strict
progression rather than setup cost.

### run_pending_memory

Builds a fresh in-memory Scheduler with a set of schedules due at the same instant.

Setup is performed before the timer starts. The measurement covers one
`Scheduler.run_pending()` cycle that materializes and executes every due schedule.

### run_pending_sqlite

Uses the same due-work concept with `SqliteUnitOfWorkFactory`.

Database creation and schedule setup happen before the timer starts. The measured region is
one due `run_pending()` cycle.

### run_pending_memory_idle_<count>

Builds future, non-due in-memory schedules, crosses startup barriers once, then measures
steady-state idle `run_pending()` scans without target execution.

The smoke profile compares 100 vs 1,000 schedules. The standard profile compares 1,000 vs
10,000 schedules and records:

```text
large idle median / small idle median
```

This ratio is evidence for T-PERF-002. It is **reported, not used as a hard CI threshold**.


## Measurement rules

For each benchmark:

```text
fresh sample setup
      ↓
start perf_counter()
      ↓
measured operation(s)
      ↓
stop perf_counter()
      ↓
repeat
      ↓
median + min + max
```

The report records:

- PyScheduleKit source version;
- Python version and implementation;
- platform string;
- workload profile;
- operations and repeats;
- median/min/max seconds;
- median-derived operations per second.

## CI policy

Normal pytest runs the small `smoke` evidence profile through
`tests/acceptance/test_benchmark_harness.py`.

The harness reports the 1k→10k idle-scan ratio as **scale evidence** for T-PERF-002, but
does not fail CI from a wall-clock or ratio threshold. Shared runners vary in CPU scheduling,
host contention, virtualization and thermal state.

Raw timing and scaling evidence remain review material rather than direct product guarantees.
The V1 performance specification can later promote a ratio into a controlled guardrail once
enough history exists on a comparable runner.

## Workflow

Automatic baseline:

```text
benchmark-relevant merge to main
        ↓
standard profile / Python 3.13
        ↓
JSON + Markdown artifacts (30 days)
```

Manual run:

```text
Actions → Performance Benchmarks → Run workflow
```

Inputs:

- profile: `smoke` or `standard`
- Python: 3.11 / 3.12 / 3.13

The workflow publishes:

- `benchmark-results.json`
- `benchmark-results.md`
- the Markdown report in the GitHub Actions job summary

Artifacts are retained for 30 days.

## Comparing runs

Only compare reports when the following remain equivalent:

```text
profile
Python version
Python implementation
runner/OS class
PyScheduleKit workload semantics
```

Prefer medians over single-run values.

A meaningful regression investigation should first reproduce locally or on a controlled
runner before changing code.

## Future evolution

Once PyScheduleKit reaches a stable operational workload and a controlled benchmark runner
exists, this harness can evolve toward:

- committed historical baselines;
- percentile distributions;
- memory/allocation measurements;
- scale curves rather than one fixed workload;
- controlled regression budgets;
- broader composite fan-out curves;
- multi-worker throughput and lease-contention benchmarks.

Those belong after evidence exists; POST-05 intentionally establishes the measurement
foundation first.

## Relationship to publication

Benchmarks operate on the source development version and do not require PyPI.

```text
pre-1.0:
    code → CI → dogfood → benchmark → harden

1.0+:
    code → CI → dogfood → benchmark → release readiness → publish
```
