# 0.2.x — PostgreSQL Persistence

PostgreSQL is the first milestone of the **Execution & Storage Ecosystem** roadmap.

The goal is not to create a second persistence model. PostgreSQL must implement the same
observable `UnitOfWorkFactory` contract already qualified for InMemory and SQLite.

## Driver decision

PG-00 uses **Psycopg 3**.

Project dependency policy:

```text
base install
    pyschedulekit
    → still zero runtime dependencies

PostgreSQL consumer
    pyschedulekit[postgres]
    → psycopg[binary]>=3.3.6,<4
```

Connection pooling is deliberately deferred. Psycopg pooling is a separate capability and
is not necessary to prove repository semantics.

## PostgreSQL-specific rules

### Native time

Temporal query fields use:

```sql
TIMESTAMPTZ
```

Examples:

- `schedules.next_run_time`;
- `execution_requests.scheduled_at`;
- `executions.next_attempt_at`;
- lease/claim expiry;
- retention horizons.

### Versioned structured snapshots

Existing codec payloads remain `TEXT`:

```text
definition_json
policy_json
retry_json
result_json
payload_json
```

This preserves one serialization contract across SQLite and PostgreSQL instead of creating a
PostgreSQL-only JSONB codec path before parity exists.

### Bootstrap serialization

SQLite uses `BEGIN IMMEDIATE`.

PostgreSQL PG-00 uses a **transaction-scoped advisory lock**:

```text
transaction
    ↓
pg_advisory_xact_lock(project-key)
    ↓
metadata check
    ↓
schema create / verify
    ↓
commit or rollback
```

The lock disappears automatically at transaction end.

### Fail closed

If PostgreSQL reports a schema version that this adapter does not understand, bootstrap
raises immediately.

PG-00 does not attempt speculative migrations.

## Schema foundation

The initial PostgreSQL schema models the current durable surface:

```text
pyschedulekit_schema
schedules
execution_requests
executions
attempts
outbox_messages
execution_claims
schedule_admission_locks
schedule_materialization_leases
```

The relational invariants include:

- foreign keys;
- natural uniqueness;
- lifecycle CHECK constraints;
- optimistic version columns;
- fencing generations;
- retention timestamps and indexes.

## Delivery lots

### PG-00 — Contract & CI Foundation ✅

- optional Psycopg dependency;
- live PostgreSQL CI service;
- PostgreSQL DDL;
- native `TIMESTAMPTZ`;
- transaction advisory-lock bootstrap;
- idempotent bootstrap;
- concurrent bootstrap qualification;
- unsupported-version fail-closed behavior.

No public PostgreSQL factory yet.

### PG-01 — Core Repositories ✅

Implement:

- ScheduleRepository;
- ExecutionRequestRepository;
- ExecutionRepository;
- AttemptRepository;
- PostgreSQL UnitOfWork staging / identity map / transaction boundary.

Exit criteria:

- round-trip core graph;
- rollback;
- duplicate translation;
- optimistic CAS;
- due/runnable queries.

### PG-02 — Coordination / Outbox / Retention ✅

Implement:

- ExecutionClaimRepository;
- ScheduleAdmissionLockRepository;
- ScheduleMaterializationLeaseRepository;
- OutboxRepository;
- RetentionRepository.

Exit criteria:

- lease acquisition/takeover;
- fencing generations;
- outbox retry state;
- bounded cleanup.

### PG-03 — Adapter Parity Contract ✅

Refactor the existing shared persistence contract so:

```text
InMemory
SQLite
PostgreSQL
```

must satisfy the same observable behavior.

This is the gate before public exposure.

### PG-04 — Scheduler / Multi-worker E2E ✅

Qualify:

- `Scheduler.run_pending()`;
- retry;
- recovery;
- reconciliation;
- outbox;
- two workers sharing PostgreSQL;
- admission / claim / materialization contention.

### PG-05 — Production Hardening 🚧 current

Qualify and document:

- isolation assumptions;
- lock ordering;
- deadlock / serialization retry policy;
- connection lifecycle;
- optional pooling;
- migration discipline;
- PostgreSQL version support matrix;
- benchmark comparison against SQLite.

PG-03/PG-04 clear the behavioral gate. `PostgresUnitOfWorkFactory` remains internal until
PG-05 closes isolation, lock/retry, connection-lifecycle and migration hardening.

## Coverage policy

The base package keeps its global branch-aware coverage floor at **85%** and excludes the
optional PostgreSQL implementation modules from that calculation.

PostgreSQL owns a dedicated live-service coverage surface:

```text
PG-01 baseline: 66.88%
PG-02 baseline: 78.45%
PG-03 qualified: 87.88%
PG-04 qualified: 88.59% / 138 live tests
current floor: 85%
```

PG-03 reached the project-level 85% standard and PG-04 qualified the public Scheduler plus
multi-worker semantics on live PostgreSQL. The 85% floor remains permanent. Public factory
exposure is deliberately deferred through PG-05 so production assumptions are documented and tested.

## PG-00 CI

Dedicated workflow:

```text
.github/workflows/postgres.yml
```

It starts a real PostgreSQL service and proves:

1. all current durable tables are created;
2. bootstrap is idempotent;
3. eight concurrent initializers converge;
4. an unknown schema version fails closed;
5. temporal columns use native `TIMESTAMPTZ`;
6. PostgreSQL remains an optional install extra.

## Local PG-00 qualification

With a PostgreSQL database available:

```bash
export PYSCHEDULEKIT_TEST_POSTGRES_DSN='postgresql://postgres@localhost:5432/pyschedulekit'
pip install -e ".[dev,postgres]"
pytest -q tests/integration/postgres
```

## Non-goals of PG-00

PG-00 does **not** provide:

- a working PostgreSQL UnitOfWork;
- repository CRUD;
- Scheduler execution on PostgreSQL;
- a public `PostgresUnitOfWorkFactory`;
- pooling;
- async persistence;
- PostgreSQL migrations from historical SQLite schema versions.

Those guarantees belong to the later PG lots and must not be implied early.

---

**Current phase:** 0.2.x — PostgreSQL / PG-03.
