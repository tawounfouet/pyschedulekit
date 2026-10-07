# LOT-22 — Transactions / DB Constraints

## Goal

Harden the SQLite persistence layer so relational integrity and optimistic concurrency are enforced by the database transaction itself, not only by Python-side validation.

LOT-22 keeps the existing domain and application model unchanged.

## Responsibility split

```text
Domain
→ business invariants and lifecycle semantics

Repositories / UnitOfWork
→ identity maps, write-sets, mapping, transactional orchestration

Database
→ structural invariants, uniqueness, references, compare-and-swap
```

The database is a final integrity boundary, not a replacement for the domain.

## Schema version

LOT-22 introduces:

```text
SCHEMA_VERSION = 2
```

A LOT-21 schema v1 database is automatically migrated to v2.

The migration is transactional:

```text
BEGIN IMMEDIATE
    ↓
rename v1 tables
    ↓
create v2 constrained tables
    ↓
copy data
    ↓
foreign_key_check
    ↓
replace schema version
    ↓
COMMIT
```

If any step fails, the migration rolls back.

## Foreign keys

SQLite foreign-key enforcement is enabled on every persistence connection:

```sql
PRAGMA foreign_keys = ON
```

Relationships are enforced:

```text
execution_requests.schedule_id
    → schedules.id

executions.request_id
    → execution_requests.id

attempts.execution_id
    → executions.id
```

References use `ON DELETE RESTRICT`.

The current persistence model does not expose aggregate deletion, so accidental orphaning is rejected.

## Natural uniqueness

Database-native unique constraints now protect logical identities:

```text
ExecutionRequest
UNIQUE(schedule_id, schedule_revision, scheduled_at)

Execution
UNIQUE(request_id)
UNIQUE(idempotency_key)

Attempt
UNIQUE(execution_id, number)
```

These guarantees remain valid even if two processes race beyond application-level duplicate checks.

## CHECK constraints

The relational schema rejects structurally impossible persisted states.

### Schedule

```text
revision >= 1
persistence_version >= 0
state in known Schedule states

ACTIVE
→ next_run_time IS NOT NULL

non-ACTIVE
→ next_run_time IS NULL
```

### ExecutionRequest

```text
schedule_revision >= 1
version >= 0
timeout_seconds IS NULL OR > 0
known lifecycle state
non-empty target fields
```

### Execution

```text
version >= 0
attempt_count >= 0
known lifecycle state

RUNNING
↔ active_attempt_number IS NOT NULL

RETRY_WAIT
↔ next_attempt_at IS NOT NULL

terminal state
↔ result_json IS NOT NULL
```

### Attempt

```text
number >= 1
version >= 0
known lifecycle state

RUNNING
↔ result_json IS NULL

terminal state
↔ result_json IS NOT NULL
```

## Compare-and-swap updates

LOT-21 validated optimistic versions before issuing an UPDATE.

LOT-22 also places the expected version in the SQL predicate.

Example:

```sql
UPDATE executions
SET ..., version = ?
WHERE id = ?
  AND version = ?
```

The repository requires:

```text
cursor.rowcount == 1
```

Otherwise:

```text
OptimisticConcurrencyError
```

This closes the semantic gap between:

```text
validate stored version
        ↓
concurrent change
        ↓
unconditional UPDATE
```

The same CAS approach applies to:

- Schedule.persistence_version;
- ExecutionRequest.version;
- Execution.version;
- Attempt.version.

## Transaction atomicity

A UnitOfWork commit remains one SQL transaction:

```text
BEGIN IMMEDIATE
    ↓
validate repositories
    ↓
apply Schedule writes
    ↓
apply ExecutionRequest writes
    ↓
apply Execution writes
    ↓
apply Attempt writes
    ↓
COMMIT
```

If a late database constraint fails:

```text
ROLLBACK
```

including writes already executed earlier in that same UnitOfWork.

Example:

```text
insert valid Schedule
insert orphan ExecutionRequest
    ↓
FOREIGN KEY failure
    ↓
rollback
    ↓
neither record is committed
```

## Constraint error mapping

SQLite `IntegrityError` values are translated back into persistence-port semantics.

```text
Schedule unique violation
→ DuplicateScheduleError

ExecutionRequest unique violation
→ DuplicateExecutionRequestError

Execution unique violation
→ DuplicateExecutionError

Attempt unique violation
→ DuplicateAttemptError

FOREIGN KEY violation
→ ReferentialIntegrityError

CHECK violation
→ DatabaseInvariantError
```

Unknown integrity failures remain `PersistenceConflictError`.

## Migration safety

The v1 → v2 migration validates foreign keys before committing.

A legacy database containing orphaned relationships therefore does not silently become a nominal v2 database.

The migration fails instead of blessing inconsistent durable state.

## Safety properties

1. foreign keys are enabled on every SQLite connection;
2. natural logical identities are database-unique;
3. lifecycle structural invariants have CHECK constraints;
4. optimistic updates are true SQL compare-and-swap operations;
5. multi-repository commits remain atomic;
6. late constraint failures roll back earlier writes in the transaction;
7. relational errors map to explicit persistence-port exceptions;
8. LOT-21 databases migrate automatically from schema v1 to v2;
9. migration failure leaves the prior database transaction uncommitted;
10. domain invariants remain the primary business model.

## Qualification

LOT-22 qualifies:

- foreign-key violation mapping;
- atomic rollback after a late multi-repository failure;
- database-native OccurrenceKey uniqueness;
- invalid Schedule state rejection;
- ACTIVE Schedule checkpoint constraint;
- foreign-key PRAGMA on factory connections;
- v1 → v2 migration with retained Schedule data;
- post-migration v2 CHECK enforcement;
- existing optimistic-concurrency tests;
- existing Scheduler SQLite E2E regression coverage.

## Non-goals

LOT-22 does not yet implement:

- crash recovery;
- stale RUNNING reconciliation;
- lease ownership;
- worker claims;
- distributed locking;
- outbox delivery;
- schema migration tooling beyond the built-in v1 → v2 transition;
- PostgreSQL-specific transaction semantics.

## Next

`LOT-23 — Crash Recovery`
