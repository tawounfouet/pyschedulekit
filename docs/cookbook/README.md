# PyScheduleKit Cookbook

POST-02 turns the qualified public API into small, runnable scenarios.

The examples deliberately use deterministic clocks and local resources so they can be run
without network access, credentials, or sleeps.

## Run all examples

From the repository root:

```bash
python examples/01_interval_quickstart.py
python examples/02_cron_timezone.py
python examples/03_retry_backoff.py
python examples/04_sqlite_durability.py
python examples/05_operational_health.py
```

They are also executed by
[`tests/acceptance/test_cookbook_examples.py`](../../tests/acceptance/test_cookbook_examples.py).

## 1. Interval quickstart

**Scenario:** run one heartbeat every five minutes.

[Source](../../examples/01_interval_quickstart.py)

Core ideas:

- inject a `MutableClock`;
- create an `IntervalTrigger`;
- register a callable directly through `Scheduler.add_schedule()`;
- call `run_pending()` explicitly;
- advance virtual time instead of sleeping.

```python
scheduler.add_schedule(
    id="heartbeat",
    target=heartbeat,
    trigger=IntervalTrigger(
        every=Duration.minutes(5),
        anchor=start.add(Duration.minutes(5)),
    ),
)
```

Use this pattern for deterministic application tests and simple embedded scheduling.

## 2. Cron with an explicit timezone

**Scenario:** run at 09:00 on weekdays in Paris.

[Source](../../examples/02_cron_timezone.py)

```python
CronTrigger(
    "0 9 * * 1-5",
    timezone=Timezone("Europe/Paris"),
)
```

Cron rules model civil calendar time. The timezone belongs to the trigger semantics and
must remain explicit when DST behavior matters.

## 3. Retry with fixed backoff

**Scenario:** a dependency fails once, then succeeds five minutes later.

[Source](../../examples/03_retry_backoff.py)

```python
RetryPolicy(
    max_attempts=3,
    backoff=FixedBackoff(Duration.minutes(5)),
)
```

The example proves two useful properties:

1. the first failure schedules a retry rather than immediately failing the execution;
2. calling `run_pending()` before the retry deadline performs no duplicate attempt.

Use retries only for work that can tolerate repeated execution and make side effects
idempotent whenever possible.

## 4. SQLite durability

**Scenario:** execute a schedule, reopen the database, and inspect its next run.

[Source](../../examples/04_sqlite_durability.py)

```python
scheduler = Scheduler(
    clock=clock,
    uow_factory=SqliteUnitOfWorkFactory(database),
)
```

The schedule definition and operational checkpoint are durable. Python callables themselves
remain process-local registrations; after a process restart, re-register trusted local
targets before attempting to execute them again.

This separation is intentional:

```text
durable schedule metadata       → SQLite
trusted executable Python code  → process-local registry
```

## 5. Health and readiness

**Scenario:** expose liveness separately from startup readiness.

[Source](../../examples/05_operational_health.py)

`Scheduler.health()` answers whether the persistence boundary is available and reports
runtime/process state.

`Scheduler.readiness()` is stricter. A fresh Scheduler is not ready until startup safety
barriers — recovery and reconciliation — have completed. The first `run_pending()` crosses
those barriers automatically.

This distinction maps naturally to service probes:

```text
liveness/readiness endpoint
├── health()      → process/persistence health
└── readiness()   → safe to accept scheduling work
```

## Choosing a pattern

| Need | Start with |
|---|---|
| periodic local work | [Interval quickstart](../../examples/01_interval_quickstart.py) |
| wall-clock business calendar | [Cron + timezone](../../examples/02_cron_timezone.py) |
| transient dependency failures | [Retry/backoff](../../examples/03_retry_backoff.py) |
| durable local persistence | [SQLite durability](../../examples/04_sqlite_durability.py) |
| operational probes | [Health/readiness](../../examples/05_operational_health.py) |

## Cookbook constraints

Examples in this directory follow the same project rules as production code:

- public API first;
- deterministic time where possible;
- no external credentials;
- no network dependency;
- no hidden environment configuration;
- executable under CI;
- no claim that PyPI contains the current development version.

The last public PyPI prerelease remains `0.1.0a3`; cookbook development follows the source
tree until stable `1.0.0`.
