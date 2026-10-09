# POST-04 — Installed-package Dogfooding

POST-04 validates PyScheduleKit as a **consumer would use it**, without publishing a new
package to PyPI.

The dogfood application lives in
[`dogfood/consumer_app.py`](../../dogfood/consumer_app.py).

## What makes this different from the cookbook

The cookbook runs examples from the repository development environment.

POST-04 runs after a wheel or source distribution has been built and installed into the
clean qualification environment.

The workflow then changes directory to `/tmp` and executes the consumer app by absolute
script path:

```text
build wheel / sdist
      ↓
install artifact
      ↓
pip check
      ↓
cd /tmp
      ↓
smoke installed package
      ↓
dogfood installed package
```

The dogfood script additionally verifies that `pyschedulekit.__file__` is **not located
under the GitHub source checkout**.

## Qualification matrix

```text
wheel × Python 3.11
wheel × Python 3.12
wheel × Python 3.13
sdist × Python 3.11
sdist × Python 3.12
sdist × Python 3.13
```

Every cell executes the same consumer application.

## Scenario

The consumer application simulates a small operational service using SQLite.

### 1. Cron business event

A weekday Paris schedule runs at 09:00 local time using:

- `CronTrigger`
- `Timezone("Europe/Paris")`

### 2. Periodic synchronization

A second job uses `IntervalTrigger` with a 15-minute cadence.

Its first attempt raises a simulated transient dependency failure.

### 3. Retry

The synchronization job uses:

- `RetryPolicy(max_attempts=3)`
- `FixedBackoff(Duration.minutes(2))`

The application proves that the first attempt schedules a retry and the second attempt
succeeds after the deterministic two-minute advance.

### 4. SQLite durability

Both schedules use `SqliteUnitOfWorkFactory`.

After the run, a fresh `Scheduler` instance reopens the same database and inspects both
schedules successfully.

### 5. Operational readiness

The consumer checks:

- `Scheduler.readiness()` before startup barriers;
- `Scheduler.readiness()` after the first cycle;
- `Scheduler.health()` after execution.

## Why this is meaningful

POST-04 catches failures that repository unit/e2e tests can miss:

- missing packaged files;
- import behavior that only works from the source checkout;
- wheel/sdist packaging divergence;
- public API assumptions hidden by internal imports;
- installed SQLite/runtime behavior regressions;
- Python-version-specific installation/runtime failures.

## PyPI policy

No new PyPI publication is required.

Dogfooding uses the exact artifacts produced by Distribution Qualification. This preserves
the project policy:

```text
pre-1.0:
    build → install → dogfood → qualify

stable >=1.0.0:
    build → install → dogfood → readiness → publish
```

The last public prerelease remains `0.1.0a3`.
