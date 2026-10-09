# PyScheduleKit Cookbook

This cookbook contains small **executable scenarios** built from the same public surfaces
qualified by the test suite.

The examples deliberately avoid external services and wall-clock sleeps so they remain
fast, deterministic and useful as both documentation and regression evidence.

## Run an example

From the repository root:

```bash
python examples/cookbook/01_interval_quickstart.py
python examples/cookbook/02_cron_timezone.py
python examples/cookbook/03_retry_backoff.py
python examples/cookbook/04_sqlite_durable.py
python examples/cookbook/05_operations_health.py
```

With the project installed from a checkout:

```bash
pip install -e .
```

## Scenario map

| Example | What it demonstrates | Key API |
|---|---|---|
| [01 — Interval quickstart](./01_interval_quickstart.py) | deterministic scheduling without sleeping | `Scheduler`, `IntervalTrigger`, `MutableClock` |
| [02 — Cron + timezone](./02_cron_timezone.py) | civil-time scheduling in Europe/Paris | `CronTrigger`, `Timezone` |
| [03 — Retry + backoff](./03_retry_backoff.py) | transient failure followed by a delayed retry | `RetryPolicy`, `FixedBackoff` |
| [04 — Durable SQLite](./04_sqlite_durable.py) | persistence across Scheduler instances | `SqliteUnitOfWorkFactory`, `register_target` |
| [05 — Operations / health](./05_operations_health.py) | readiness, health, inspect, pause/resume | operational Scheduler API |

## 01 — Interval quickstart

The smallest useful vertical slice is:

```text
MutableClock
    ↓
IntervalTrigger(every=10m)
    ↓
Scheduler.add_schedule()
    ↓
advance time
    ↓
Scheduler.run_pending()
    ↓
one successful execution
```

The clock is explicit, so the example proves scheduling behavior without a real ten-minute
wait.

## 02 — Cron + timezone

Cron is calendar scheduling, not elapsed-duration scheduling.

The example starts at:

```text
2026-01-05 07:59 UTC
          =
2026-01-05 08:59 Europe/Paris
```

and schedules:

```text
0 9 * * 1-5
```

After advancing one minute, the weekday 09:00 Paris occurrence is due.

For DST-sensitive applications, keep the timezone on the `CronTrigger`; do not duplicate
conflicting timezone metadata on the Schedule.

## 03 — Retry + fixed backoff

The target fails once and succeeds on its second invocation.

```text
attempt 1
    ↓ failure
RETRY_WAIT
    ↓ +5 minutes
attempt 2
    ↓
SUCCESS
```

The example explicitly shows that calling `run_pending()` again **before** the backoff
deadline does not execute the target.

## 04 — Durable SQLite

SQLite persists scheduling state, but Python callables remain process-local trusted code.

That means a restarted process does this:

```text
open same SQLite database
        +
register trusted callable under the same TargetRef
        ↓
inspect / execute persisted Schedule state
```

The persisted Schedule contains the declarative reference `jobs:daily-sync`, not a
serialized Python function.

This separation is intentional and is important for restart safety.

## 05 — Operations / health

The operational surface distinguishes liveness from readiness:

- `health()` checks process/persistence liveness information;
- `readiness()` is false before startup recovery/reconciliation barriers have completed;
- one scheduling cycle crosses those barriers;
- `inspect_schedule()`, `pause_schedule()` and `resume_schedule()` expose immutable
  operational snapshots.

## Why MutableClock appears in examples

`MutableClock` is a shipped testing helper under `pyschedulekit.testing`.

It lets examples express:

```python
clock.advance(Duration.minutes(10))
```

instead of:

```python
sleep(600)
```

The scheduling semantics are therefore deterministic and the examples remain suitable for
CI.

## Qualification

The cookbook is executable documentation.

`tests/acceptance/test_cookbook_examples.py` runs every example with
`runpy.run_path(..., run_name="__main__")` and checks its observable output.

A cookbook script that stops working therefore fails CI.

## Scope

POST-02 focuses on common real-world entry points. It does **not** try to document every
public class or method.

That belongs to POST-03 — API Documentation.

---

**Status:** POST-02 — Real-world Examples / Cookbook.
