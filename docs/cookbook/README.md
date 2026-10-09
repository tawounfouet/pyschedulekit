# PyScheduleKit — Real-world Cookbook

POST-02 turns the public API into executable usage scenarios. Every Python file referenced
below is run by the acceptance suite, so these recipes are maintained as code rather than
documentation-only snippets.

## 1. One-shot reporting job

**Use when:** a report, export or migration step must run once at a known instant.

Run:

```bash
python examples/one_shot_job.py
```

Source: [`examples/one_shot_job.py`](../../examples/one_shot_job.py).

The recipe combines:

```text
DateTrigger
    ↓
one durable Schedule
    ↓
run_pending before due → no-op
    ↓
run_pending at due → one SUCCESS
```

The important property is finiteness: after the single occurrence has been materialized,
the DateTrigger has no later occurrence.

## 2. Anchored recurring refresh

**Use when:** a cache, catalog or dataset must refresh every fixed elapsed interval.

Run:

```bash
python examples/recurring_interval.py
```

Source: [`examples/recurring_interval.py`](../../examples/recurring_interval.py).

`IntervalTrigger` is fixed-rate and anchored. A ten-minute schedule means:

```text
10:10
10:20
10:30
...
```

Execution duration never shifts the recurrence anchor. This is appropriate when the
schedule itself matters more than "ten minutes after the previous completion."

## 3. Weekday business-time cron

**Use when:** work is expressed in civil time, for example "09:00 Paris, Monday–Friday."

Run:

```bash
python examples/business_cron.py
```

Source: [`examples/business_cron.py`](../../examples/business_cron.py).

The recipe makes the timezone explicit:

```python
CronTrigger(
    "0 9 * * 1-5",
    timezone=Timezone("Europe/Paris"),
)
```

Prefer CronTrigger for calendar rules and IntervalTrigger for elapsed-duration rules.
PyScheduleKit resolves cron occurrences against IANA timezone data instead of assuming UTC
or the host machine timezone.

## 4. Timeout with controlled retry

**Use when:** a transient integration may exceed its execution budget and should retry only
under an explicit policy.

Run:

```bash
python examples/retry_after_timeout.py
```

Source: [`examples/retry_after_timeout.py`](../../examples/retry_after_timeout.py).

The scenario snapshots both policies onto the execution:

```text
timeout = 2 seconds
max_attempts = 2
fixed_backoff = 5 minutes

attempt 1 → TIMED_OUT
              ↓
          RETRY_WAIT
              ↓ 5m
attempt 2 → SUCCESS
```

Retry is attached to the logical Execution: the second attempt keeps the same execution
identity while incrementing the attempt count.

## 5. SQLite durability and restart

**Use when:** schedules must survive process restarts.

Run:

```bash
python examples/sqlite_restart.py
```

Source: [`examples/sqlite_restart.py`](../../examples/sqlite_restart.py).

The durable database stores schedule/execution state, while Python callables remain trusted
process-local objects. After restart the application therefore re-registers the same target
reference before executing the next occurrence.

```text
process A
  register "refresh-catalog"
  persist Schedule → SQLite
  execute 10:10
        ↓ restart
process B
  open same SQLite file
  register "refresh-catalog" again
  inspect next_run_time = 10:20
  execute 10:20
```

This separation is intentional: persisted target references never authorize arbitrary
Python imports.

## 6. Operational controls

**Use when:** an operator needs to inspect or control a schedule without exposing mutable
domain aggregates.

Run:

```bash
python examples/operational_controls.py
```

Source: [`examples/operational_controls.py`](../../examples/operational_controls.py).

The public facade supports immutable operational snapshots and explicit controls:

```text
inspect_schedule
      ↓
pause_schedule
      ↓
resume_schedule
      ↓
run_pending
      ↓
cancel_schedule
```

A paused schedule does not materialize new occurrences. Resuming recalculates the next
occurrence from the scheduler clock rather than replaying elapsed wall time blindly.

## Choosing the right recipe

| Need | Start with |
|---|---|
| run exactly once | DateTrigger / one-shot |
| repeat every elapsed duration | IntervalTrigger |
| run at business/calendar time | CronTrigger + Timezone |
| tolerate transient failure | RetryPolicy + explicit backoff |
| bound execution time | timeout + retry policy if appropriate |
| survive restart | SqliteUnitOfWorkFactory + target re-registration |
| pause/resume/cancel safely | Scheduler operational API |

## Testing philosophy

The examples use `MutableClock` only to make time deterministic. They are not mock
implementations of the scheduler: each recipe goes through the same public `Scheduler`
facade, trigger policies, execution lifecycle and persistence adapters used by consumers.

The acceptance test [`test_cookbook_examples.py`](../../tests/acceptance/test_cookbook_examples.py)
executes every `examples/*.py` recipe with `runpy`.

## Next

POST-03 will document the public API systematically. The cookbook should remain
task-oriented; API reference documentation should remain contract-oriented.
