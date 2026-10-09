# POST-05 — Performance Baselines

PyScheduleKit performance qualification follows the V1 test specification:

> do not target one universal absolute benchmark; establish reproducible guardrails.

The executable harness is [`benchmarks/run_baseline.py`](../../benchmarks/run_baseline.py).

## What is measured

### T-PERF-001 — bounded IntervalTrigger calculation

The same `IntervalTrigger.next_after()` operation is measured for:

- a reference one day after the anchor;
- a reference ten years after the anchor.

Because interval lookup is arithmetic rather than occurrence-by-occurrence replay, the far
reference should remain in the same complexity class as the near reference.

The guardrail is intentionally loose:

```text
far median / near median <= 50
```

This is not a latency SLA. It is a catastrophe detector.

### T-PERF-002 — 10k in-memory schedules

The harness builds schedulers with 1,000 and 10,000 future schedules, crosses startup
recovery/reconciliation once, then measures steady-state idle `run_pending()` cycles.

The dimensionless scaling guardrail is:

```text
10k idle-cycle median / 1k idle-cycle median <= 30
```

Linear scanning should be around an order of magnitude. The threshold leaves substantial
runner noise while still detecting severe superlinear regression.

## Profiles

```text
smoke
  interval: 2,000 calls / repeat
  schedules: 100 + 1,000
  repeats: 3

ci
  interval: 20,000 calls / repeat
  schedules: 1,000 + 10,000
  repeats: 5

full
  interval: 100,000 calls / repeat
  schedules: 1,000 + 10,000 + 50,000
  repeats: 9
```

## Run locally

```bash
python -m benchmarks.run_baseline --profile smoke
python -m benchmarks.run_baseline --profile ci --assert-guardrails
python -m benchmarks.run_baseline \
  --profile full \
  --output benchmark-results.json
```

## Output

The harness emits JSON containing:

- Python version and implementation;
- per-call near/far interval timings;
- near/far ratio;
- schedule population setup time;
- idle-cycle min/median/max;
- 10k/1k idle-cycle ratio.

The JSON artifact is retained by the Performance Baseline workflow so results can be
compared across commits without baking one runner's milliseconds into product semantics.

## CI policy

POST-05 separates **correctness gates** from **performance evidence**:

- ordinary pytest still proves semantic correctness;
- a small harness test proves the benchmark code itself;
- the dedicated workflow executes the `ci` profile and ratio guardrails;
- raw JSON is uploaded as an artifact.

The ratio guardrails are deliberately broad. Tight performance budgets should only be added
after enough historical baseline data exists.

## Remaining PERF scenarios

The V1 spec also lists:

- T-PERF-003 — bounded catch-up memory;
- T-PERF-004 — telemetry cardinality;
- T-PERF-005 — runtime idle / no busy-loop;
- T-PERF-006 — backlog fairness;
- future load / thundering-herd scenarios.

POST-05 establishes the benchmark infrastructure and first two baselines. POST-06 can reuse
it while injecting faults and runtime pressure.

---

**Status:** POST-05 — Performance Benchmarks.
