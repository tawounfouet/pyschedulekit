# PyScheduleKit Examples / Cookbook

These examples are small **executable scenarios** built from the same public surfaces
qualified by the test suite.

They avoid external services and wall-clock sleeps so they remain deterministic, fast and
useful as both documentation and regression evidence.

## Run the examples

From the repository root:

```bash
python examples/01_interval_quickstart.py
python examples/02_cron_timezone.py
python examples/03_retry_backoff.py
python examples/04_sqlite_durability.py
python examples/05_operational_health.py
```

Install the project from a checkout first:

```bash
pip install -e .
```

## Scenario map

| Example | What it demonstrates | Key API |
|---|---|---|
| [01 — Interval quickstart](./01_interval_quickstart.py) | deterministic scheduling without sleeping | `Scheduler`, `IntervalTrigger`, `MutableClock` |
| [02 — Cron + timezone](./02_cron_timezone.py) | civil-time scheduling in Europe/Paris | `CronTrigger`, `Timezone` |
| [03 — Retry + backoff](./03_retry_backoff.py) | transient failure followed by delayed retry | `RetryPolicy`, `FixedBackoff` |
| [04 — Durable SQLite](./04_sqlite_durability.py) | persisted schedule state across Scheduler instances | `SqliteUnitOfWorkFactory` |
| [05 — Operational health](./05_operational_health.py) | startup readiness and liveness | `health()`, `readiness()` |

## 01 — Interval quickstart

The smallest useful vertical slice is:

```text
MutableClock
    ↓
IntervalTrigger
    ↓
Scheduler.add_schedule()
    ↓
advance time
    ↓
Scheduler.run_pending()
    ↓
one successful execution
```

The clock is explicit, so the example proves scheduling behavior without a real wait.

## 02 — Cron + timezone

Cron is calendar scheduling rather than elapsed-duration scheduling.

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

After advancing one minute, the Monday 09:00 Paris occurrence is due.

For DST-sensitive applications, keep the timezone on the `CronTrigger`; do not duplicate
conflicting timezone metadata on the Schedule.

## 03 — Retry + fixed backoff

The target fails once and succeeds on its second invocation:

```text
attempt 1
    ↓ failure
RETRY_WAIT
    ↓ +5 minutes
attempt 2
    ↓
SUCCESS
```

The script also proves that another `run_pending()` before the retry deadline does not
execute work.

## 04 — Durable SQLite

SQLite persists scheduling state. The example executes a schedule, opens the same database
through a second `Scheduler`, and verifies that the next run time survived the reopen.

One important boundary remains:

> Python callables are process-local trusted code; durable state stores declarative target
> references, not serialized Python functions.

A real restarted process must therefore register trusted Python targets again before those
targets can execute.

## 05 — Operational health

The operational API distinguishes liveness from readiness:

- `health()` reports persistence/process liveness;
- `readiness()` is false before startup recovery and reconciliation;
- the first scheduling cycle crosses those barriers;
- readiness then becomes true.

## Why MutableClock appears here

`MutableClock` is a shipped helper under `pyschedulekit.testing`.

It lets examples express:

```python
clock.advance(Duration.minutes(5))
```

instead of sleeping for five minutes. This keeps the examples deterministic and CI-safe.

## Executable documentation

`tests/acceptance/test_cookbook_examples.py` launches each file in a subprocess and checks
its observable output.

A broken cookbook scenario therefore fails normal CI.

## Scope

POST-02 focuses on common real-world entry points rather than exhaustive API reference.

Exhaustive public API documentation belongs to **POST-03 — API Documentation**.

---

**Status:** POST-02 — Real-world Examples / Cookbook.
