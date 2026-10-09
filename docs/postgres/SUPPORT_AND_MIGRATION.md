# PostgreSQL Support, Transactions and Migration Policy

This document is the production contract for PyScheduleKit PostgreSQL persistence.

## Public import

PostgreSQL support is an **optional stable namespace**:

```python
from pyschedulekit.postgres import (
    PostgresUnitOfWorkFactory,
    TransientPersistenceError,
)

uow_factory = PostgresUnitOfWorkFactory(
    "postgresql://scheduler@db.example.com/pyschedulekit"
)
```

Install the adapter with:

```bash
pip install "pyschedulekit[postgres]"
```

The root package intentionally does not import PostgreSQL support. Therefore:

```python
import pyschedulekit
```

continues to work with the zero-runtime-dependency base installation.

## Supported PostgreSQL majors

PyScheduleKit qualifies these PostgreSQL major versions in live CI:

| PostgreSQL | PyScheduleKit status | Upstream lifecycle |
|---|---|---|
| 16 | ✅ supported / CI-qualified | upstream supported through 2028 |
| 17 | ✅ supported / CI-qualified | upstream supported through 2029 |
| 18 | ✅ supported / CI-qualified | upstream supported through 2030 |
| 15 | ❌ not PyScheduleKit-qualified | upstream support does not imply framework support |
| 14 | ❌ not PyScheduleKit-qualified | upstream support does not imply framework support |

Reference: PostgreSQL versioning policy:
<https://www.postgresql.org/support/versioning/>

The GitHub Actions matrix uses:

```text
postgres:16-alpine
postgres:17-alpine
postgres:18-alpine
```

so qualification follows the current minor release available for each supported major.

Consumers should run the current upstream minor release for their chosen major.

## Python and driver contract

PostgreSQL support inherits the package Python support matrix:

```text
Python 3.11
Python 3.12
Python 3.13
```

Driver:

```text
psycopg[binary] >=3.3.6,<4
```

Optional pooling:

```bash
pip install "pyschedulekit[postgres-pool]"
```

The pool itself remains application-owned. PyScheduleKit accepts connection
provider/releaser hooks and returns a clean, rolled-back connection to the caller-supplied
releaser when a UnitOfWork exits.

## Transaction isolation

Every PostgreSQL UnitOfWork uses:

```text
READ COMMITTED
```

PyScheduleKit relies on:

- optimistic entity versions;
- durable fencing generations;
- unique/FK/CHECK constraints;
- deterministic write-set ordering;
- explicit transaction boundaries.

The adapter does not silently promote isolation levels.

## Lock ordering

Repository write sets are sorted by durable identity before validation/apply.

The same ordering rule is used across schedules, requests, executions, attempts, claims,
admission locks, materialization leases and outbox messages.

Purpose:

```text
same logical write set
        ↓
same durable lock acquisition order
        ↓
lower deadlock probability
```

This reduces deadlocks; it cannot prove that PostgreSQL will never abort a transaction.

## Deadlocks and serialization aborts

PostgreSQL may still abort a transaction because of a transient concurrency condition.

PyScheduleKit maps PostgreSQL:

- `DeadlockDetected`;
- `SerializationFailure`;

to:

```python
TransientPersistenceError
```

The adapter **never replays application mutations implicitly**.

Correct caller behavior is:

```text
transaction abort
      ↓
discard UnitOfWork
      ↓
start a fresh UnitOfWork
      ↓
reload durable state
      ↓
retry the whole application operation if policy allows
```

This prevents hidden duplicate side effects.

## Connection lifecycle

A UnitOfWork guarantees:

1. one acquired connection;
2. autocommit disabled;
3. READ COMMITTED isolation;
4. commit or rollback;
5. rollback again on context exit as cleanup;
6. connection close, or return through the configured releaser.

Pool lifecycle is not managed by PyScheduleKit.

The application is responsible for:

- pool sizing;
- pool startup/shutdown;
- credentials/TLS;
- connection timeout policy;
- server failover topology.

## Schema version

Current PostgreSQL persistence schema:

```text
SCHEMA_VERSION = 1
```

Bootstrap behavior is deliberately fail-closed:

```text
no metadata row
    → create schema v1

metadata version == 1
    → verify schema and continue

metadata version != 1
    → fail immediately
```

PyScheduleKit does not guess how to mutate an unknown schema.

## Migration discipline

There is currently **no in-place PyScheduleKit schema migration from one PostgreSQL schema
version to another**, because only schema v1 exists.

Before `SCHEMA_VERSION` may increase, the same change must provide:

1. an explicit migration path from every supported previous schema version;
2. forward migration tests on PostgreSQL 16/17/18;
3. rollback/recovery instructions;
4. backup prerequisite documentation;
5. compatibility behavior for application rollout;
6. failure tests proving unknown/partial states fail closed.

A schema-version bump without those artifacts is not releaseable.

## PostgreSQL major upgrades

Database-server major upgrades are infrastructure operations outside PyScheduleKit.

For a 16 → 17 or 17 → 18 upgrade:

1. stop or drain scheduler workers;
2. take and verify a database backup;
3. perform the PostgreSQL upgrade using the organization's approved mechanism
   (`pg_upgrade`, logical migration, dump/restore, managed-service workflow, etc.);
4. run the PyScheduleKit schema bootstrap/verification against the upgraded database;
5. run application readiness/reconciliation before restoring normal traffic.

PyScheduleKit does not automate PostgreSQL server upgrades.

## SQLite → PostgreSQL

PyScheduleKit does **not** currently provide an automated SQLite-to-PostgreSQL data migration
tool.

The two adapters share observable persistence semantics, but their physical schemas and
operational characteristics are not a promise of byte-for-byte migration compatibility.

Applications that need to move existing durable scheduler state must use an explicitly
qualified application migration procedure. Do not copy database files or issue ad-hoc table
copies and assume correctness.

A first-party cross-adapter migration tool is a separate future capability.

## Coverage and qualification

PG-05 qualification currently requires:

- shared InMemory / SQLite / PostgreSQL adapter contract;
- Scheduler E2E on PostgreSQL;
- multi-worker contention/recovery scenarios;
- branch-aware PostgreSQL coverage >=85%;
- PostgreSQL 16/17/18 live CI;
- distribution and base-install qualification;
- GitGuardian;
- benchmark smoke evidence.

Latest PG-05 branch coverage across PostgreSQL 16/17/18:

```text
88.86%
```

The support matrix and 85% floor are executable CI contracts, not documentation-only claims.

## Performance evidence

The benchmark harness can measure a PostgreSQL due-cycle and report its median ratio against
SQLite under the same profile.

These results are diagnostic evidence, **not an SLA**. Compare results only when workload,
Python version, PostgreSQL version, host class and benchmark profile remain comparable.

## Security boundary

PyScheduleKit does not own:

- PostgreSQL credentials;
- TLS certificate management;
- network ACLs;
- server roles;
- backup encryption;
- secret rotation.

Applications should inject a DSN or application-owned connection provider using their
normal secret/configuration system.

No credentials belong in PyScheduleKit source or repository configuration.

---

**Status:** PG-05 production hardening contract.
