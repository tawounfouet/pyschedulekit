# LOT-21 — SQL Persistence Foundations

## Goal

Introduce a durable SQL persistence adapter without changing the scheduling domain or the application services.

LOT-21 provides a SQLite implementation of the existing persistence ports:

```text
ScheduleRepository
ExecutionRequestRepository
ExecutionRepository
AttemptRepository
UnitOfWork
UnitOfWorkFactory
```

The in-memory adapter remains available.

## Why SQLite first

SQLite is used through Python's standard-library `sqlite3` module.

That gives LOT-21:

- zero new runtime dependency;
- real transactional SQL persistence;
- file-backed durability;
- deterministic local and CI qualification;
- a concrete relational schema before introducing database-specific integrations.

The architecture remains port-based, so later SQL adapters can reuse the same domain and application contracts.

## Public usage

```python
from pyschedulekit import Scheduler, SqliteUnitOfWorkFactory

factory = SqliteUnitOfWorkFactory("scheduler.db")

scheduler = Scheduler(
    uow_factory=factory,
)
```

The rest of the Scheduler API is unchanged.

## Relational model

LOT-21 introduces four durable tables:

```text
schedules
execution_requests
executions
attempts
```

The runtime-relevant fields remain first-class SQL columns.

Examples:

```text
schedules.state
schedules.next_run_time
schedules.persistence_version

execution_requests.state
execution_requests.scheduled_at
execution_requests.version

executions.state
executions.next_attempt_at
executions.version

attempts.state
attempts.number
attempts.version
```

This avoids hiding scheduling queries inside opaque JSON blobs.

## Structured snapshots

Complex immutable definitions are persisted as versioned JSON documents.

Examples:

```text
ScheduleDefinition
ConcurrencyPolicy
RetryPolicy
ExecutionPolicySnapshot
AttemptResult
ExecutionResult
Failure
```

The codec envelope contains an explicit version:

```json
{
  "version": 1,
  "payload": {}
}
```

Unknown codec versions fail closed.

## Trigger persistence

LOT-21 supports all built-in triggers:

```text
DateTrigger
IntervalTrigger
CronTrigger
```

Cron persistence includes:

- expression;
- timezone;
- dialect;
- ambiguous-time policy;
- nonexistent-time policy.

## Policy persistence

Schedule definitions round-trip:

- timezone;
- misfire action and grace;
- concurrency mode / max instances / overflow;
- retry attempts / retryable categories;
- NoBackoff;
- FixedBackoff;
- ExponentialBackoff;
- timeout.

## UnitOfWork semantics

The SQLite adapter intentionally mirrors the in-memory UnitOfWork.

```text
repository.add()
repository.save()
        ↓
Python write-set
        ↓
commit()
        ↓
BEGIN IMMEDIATE
        ↓
validate
        ↓
apply all repositories
        ↓
COMMIT
```

Repository mutations are not made visible merely by calling `add()` or `save()`.

## Identity map

Within one UnitOfWork:

```python
first = uow.schedules.get(schedule_id)
second = uow.schedules.get(schedule_id)

assert first is second
```

Loaded entities are tracked together with the committed version seen by that UnitOfWork.

## Optimistic concurrency

LOT-21 preserves the existing application-level version checks.

For example:

```text
UoW A reads version 3
UoW B reads version 3

UoW A commits version 4

UoW B tries to commit
    ↓
stored version != expected version
    ↓
OptimisticConcurrencyError
```

LOT-22 will harden these guarantees further with database constraints and stronger write predicates.

## SQLite transaction strategy

Each commit uses:

```sql
BEGIN IMMEDIATE
```

The repositories are validated and applied inside one SQL transaction.

This prevents partial multi-repository commits.

## Shared in-memory SQLite

For tests and embedded use:

```python
factory = SqliteUnitOfWorkFactory(":memory:")
```

The factory internally maintains a shared in-memory SQLite database so independent UnitOfWork connections observe the same committed state.

## Query parity

The SQL adapter implements the runtime queries already consumed by the application layer:

- list due schedules;
- next schedule run time;
- pending requests;
- admission candidates;
- queued Executions;
- runnable Executions;
- next retry/runnable time;
- active concurrency count per Schedule;
- Attempts for one Execution.

No application branch is required for SQLite.

## Scheduler parity

The same Scheduler stack can run with either:

```text
InMemoryUnitOfWorkFactory
or
SqliteUnitOfWorkFactory
```

`run_pending()`, retry, timeout, cancellation, continuous runtime and shutdown continue to use the persistence ports.

## Schema version

LOT-21 introduces a schema metadata table with:

```text
SCHEMA_VERSION = 1
```

A database with an unsupported schema version fails explicitly.

Migration tooling is not introduced in this lot.

## Safety properties

1. SQL persistence is behind existing ports;
2. domain objects contain no SQL concerns;
3. application services require no SQLite branches;
4. runtime query fields remain relational columns;
5. JSON snapshots are explicitly versioned;
6. writes remain staged until UnitOfWork commit;
7. multi-repository apply occurs inside one SQLite transaction;
8. optimistic versions are preserved;
9. rollback discards staged state;
10. in-memory persistence remains supported.

## Qualification

LOT-21 qualifies:

- Schedule round-trip;
- identity-map semantics;
- rollback;
- duplicate detection;
- optimistic concurrency;
- due Schedule query;
- next-run horizon;
- full ExecutionRequest → Execution → Attempt round-trip;
- shared `:memory:` SQLite;
- DateTrigger codec;
- IntervalTrigger codec;
- CronTrigger codec;
- policy/backoff codec;
- end-to-end Scheduler execution on SQLite;
- file database reopen after execution.

## Non-goals

LOT-21 does not yet implement:

- full foreign-key enforcement;
- CHECK constraints for every domain invariant;
- database-native unique constraints for every natural key;
- migrations between schema versions;
- PostgreSQL/MySQL adapters;
- connection pooling;
- crash recovery;
- reconciliation;
- outbox;
- distributed claiming.

## Next

`LOT-22 — Transactions / DB Constraints`
