# LOT-07 — In-Memory Persistence

## Goal

Introduce the first persistence boundary in PyScheduleKit without coupling the domain to a database or ORM.

The objective is not to simulate SQL perfectly.

The objective is to establish transaction semantics that the future SQLite and PostgreSQL adapters must preserve:

- explicit UnitOfWork;
- no hidden repository commit;
- commit / rollback;
- read-your-own-writes;
- committed-state isolation between independent transactions;
- deterministic due-Schedule queries;
- optimistic concurrency checks.

## Scope

LOT-07 intentionally implements only Schedule persistence.

It does not create placeholder repositories for domain objects that do not yet exist.

Therefore this lot adds:

- `ScheduleRepository` port;
- `UnitOfWork` port;
- `UnitOfWorkFactory` port;
- `InMemoryScheduleStore`;
- `InMemoryScheduleRepository`;
- `InMemoryUnitOfWork`;
- `InMemoryUnitOfWorkFactory`.

ExecutionRequest and Execution repositories will be introduced only when those domain objects exist.

## Architecture

```text
Application / future SchedulerEngine
            │
            ▼
       UnitOfWork
            │
            ▼
   ScheduleRepository
            │
      persistence port
            │
            ▼
InMemoryUnitOfWork
            │
            ▼
InMemoryScheduleStore
```

The domain still imports none of these infrastructure adapters.

## Explicit UnitOfWork

A transaction is explicit:

```python
with uow_factory() as uow:
    schedule = uow.schedules.get(schedule_id)
    ...
    uow.schedules.save(schedule)
    uow.commit()
```

Without `commit()`, staged changes are discarded.

Repository methods never commit implicitly.

## Add versus Save

The repository deliberately distinguishes:

```python
add(schedule)
```

for a new aggregate, and:

```python
save(schedule)
```

for an aggregate loaded in the current UnitOfWork.

A detached Schedule cannot be updated by simply passing an object with the same ScheduleId.

This preserves a known baseline `PersistenceVersion` for optimistic concurrency.

## Identity map

Within one UnitOfWork:

```python
repo.get(schedule_id) is repo.get(schedule_id)
```

The same tracked aggregate instance is returned.

This gives one in-transaction identity for one ScheduleId.

## Committed state is cloned

The shared in-memory store never exposes its committed Schedule instance directly.

A load creates a fresh aggregate instance containing:

- ScheduleId;
- ScheduleDefinition;
- ScheduleState;
- ScheduleRevision;
- PersistenceVersion;
- next_run_time.

Therefore a caller can mutate a loaded aggregate without mutating committed state until `save() + commit()` succeeds.

## Transaction visibility

Independent UnitOfWork instances see only committed shared state.

Example:

```text
UOW A
add Schedule X
(no commit)

UOW B
get X
→ None

UOW A
commit

UOW C
get X
→ Schedule X
```

Within its own transaction, a UnitOfWork sees its staged inserts and loaded mutations.

## Isolation level

LOT-07 does not claim full database snapshot isolation.

The in-memory model provides the semantics required by the current framework:

```text
committed shared state
+
per-UOW identity map
+
per-UOW write set
+
optimistic commit validation
```

This is closest to a deliberately small read-committed model with optimistic writes.

Future SQL adapters may provide stronger database isolation while preserving the same application contract.

## Optimistic concurrency

When a Schedule is loaded, the repository records its committed:

```text
PersistenceVersion
```

At commit:

```text
expected version
must equal
current committed version
```

Example:

```text
Store version = 0

UOW A loads version 0
UOW B loads version 0

UOW A:
pause()
version → 1
commit
Store version = 1

UOW B:
cancel()
local version → 1
commit

expected store version = 0
actual store version = 1

→ OptimisticConcurrencyError
```

The stale writer never overwrites the winner.

## Atomic validation

A UnitOfWork may contain several dirty Schedules.

Before applying any write, the in-memory adapter validates all:

- duplicate inserts;
- stale versions;
- missing committed rows.

Only after every check succeeds are changes copied into committed state.

Therefore:

> One conflict prevents every staged write in that commit from becoming visible.

This mirrors the all-or-nothing property required from future database transactions.

## PersistenceVersion semantics

The repository does not generate PersistenceVersion values.

The Schedule aggregate already owns mutation semantics.

Example:

```text
loaded version 0
pause()
Schedule version = 1
save()
commit()
persist version 1
```

The repository only verifies that version 0 was still the committed baseline when the aggregate was loaded.

## Multiple commits

The in-memory UnitOfWork supports more than one explicit commit.

After a successful commit, tracked expected versions are refreshed.

This allows:

```text
load v0
pause → v1
commit

resume → v2
commit
```

without producing a false stale-version conflict inside the same UnitOfWork.

## Rollback

`rollback()` discards:

- tracked aggregates;
- expected-version baselines;
- new IDs;
- dirty IDs.

Context exit also rolls back remaining local state.

An exception therefore cannot accidentally publish staged changes.

## Due Schedule query

The repository introduces:

```python
list_due(now=..., limit=...)
```

Eligibility:

```text
state == ACTIVE
and
next_run_time <= now
```

Ordering is deterministic:

```text
next_run_time ASC
ScheduleId ASC
```

This query is intentionally added now because it is the persistence input required by the upcoming SchedulerEngine.

## Error contracts introduced

LOT-07 introduces persistence-boundary conflicts:

- `PersistenceConflictError`;
- `OptimisticConcurrencyError`;
- `DuplicateScheduleError`;
- `UntrackedScheduleError`.

These are initial port-level errors.

The later global Error Model lot may reorganize public exposure while preserving their semantic categories.

## Qualification scenarios

LOT-07 proves:

- repository add does not commit implicitly;
- committed Schedule round-trip;
- rollback discards staged insert;
- exception on context exit rolls back;
- same UnitOfWork sees its own staged insert;
- independent UnitOfWork sees only committed state;
- loaded mutations are not persisted without explicit save;
- save + commit persists aggregate mutation;
- identity map returns the same tracked aggregate;
- detached update is rejected;
- duplicate ScheduleId is rejected;
- stale writer is rejected;
- multi-Schedule conflict validation is atomic;
- due query filters by state and time;
- due query order is deterministic;
- due query honors limit;
- future Schedules are excluded;
- staged local writes are visible to local query;
- multiple commits refresh expected versions.

## What is not persisted yet

LOT-07 does not persist:

- Occurrence as a table;
- ExecutionRequest;
- Execution;
- Attempt;
- Outbox messages;
- events or audit records.

The first SchedulerEngine only needs Schedule persistence and can still materialize its initial request representation in a later lot.

## No serialization yet

The in-memory adapter stores domain objects as in-process objects.

This is safe because no untrusted persisted bytes are being decoded.

The safe versioned JSON codec model remains required before SQLite durable definition serialization.

## Threading

The committed in-memory store uses a process-local reentrant lock for atomic commit validation and application.

This lock:

- protects the adapter's in-process committed state;
- is not a distributed coordination mechanism;
- does not change domain concurrency semantics.

## Architecture progression

```text
Trigger
  ↓
Schedule
  ↓
Occurrence
  ↓
ScheduleRepository
  ↓
UnitOfWork
  ↓
InMemory transactional store

NEXT:
SchedulerEngine
```

## Exit criteria

LOT-07 is complete when:

- repository changes never auto-commit;
- rollback leaves committed state unchanged;
- independent transactions cannot see staged state;
- stale writers cannot overwrite newer committed state;
- conflict validation is all-or-nothing;
- due Schedule selection is deterministic;
- the adapter remains replaceable behind ports;
- all Python quality gates are green.

## Next

`LOT-08 — SchedulerEngine`
