# PyScheduleKit Examples

These examples are small, deterministic programs that exercise the public scheduling API.
They are intentionally dependency-free and are executed by the repository acceptance suite.

Run any example from the repository root:

```bash
python examples/one_shot_job.py
python examples/recurring_interval.py
python examples/business_cron.py
python examples/retry_after_timeout.py
python examples/sqlite_restart.py
python examples/operational_controls.py
```

| Example | Demonstrates |
|---|---|
| [one_shot_job.py](./one_shot_job.py) | one finite DateTrigger occurrence |
| [recurring_interval.py](./recurring_interval.py) | anchored fixed-rate recurrence |
| [business_cron.py](./business_cron.py) | explicit Europe/Paris business-time cron |
| [retry_after_timeout.py](./retry_after_timeout.py) | timeout → fixed backoff → retry success |
| [sqlite_restart.py](./sqlite_restart.py) | durable schedule state across Scheduler restart |
| [operational_controls.py](./operational_controls.py) | inspect / pause / resume / run / cancel |

For the reasoning behind each scenario, see the
[Real-world Cookbook](../docs/cookbook/README.md).

## Why the examples use MutableClock

Production schedulers default to the system clock. The cookbook examples deliberately use
`MutableClock` so the same program:

- runs instantly;
- never sleeps;
- produces deterministic results;
- can be executed in CI;
- makes due-time transitions visible.

The scheduling semantics are identical; only the source of `now` is controlled.
