# V1-02.E — PostgreSQL Evolution / Rolling Upgrade

**Scope:** PostgreSQL schema evolution and worker-overlap contract for the PyScheduleKit 1.x
line.

**Current PostgreSQL schema:** v1  
**Schema migration introduced by this lot:** no  
**Package version changed:** no

## Objective

PostgreSQL schema v1 is already live-qualified on PostgreSQL 16, 17 and 18, including
multi-worker coordination, durable fencing and recovery.

V1-02.E answers the remaining production question:

> Under which conditions may old and new scheduler workers overlap against one PostgreSQL
> database during a PyScheduleKit upgrade?

The answer is intentionally conservative.

A rolling deployment is **not** automatically safe merely because two PyScheduleKit releases
are individually supported.

## Current qualification boundary

Today PyScheduleKit has only PostgreSQL schema v1.

Therefore V1-02.E can qualify:

- concurrent bootstrap of schema v1;
- simultaneous same-contract workers against schema v1;
- cross-worker read/write visibility;
- lease takeover with monotonic fencing generation;
- rejection of stale owners after takeover;
- fail-closed behavior for an unknown future schema;
- all of the above on PostgreSQL 16/17/18.

V1-02.E cannot honestly qualify a real v1→v2 rolling migration because schema v2 does not
exist.

No artificial v2 is introduced merely to satisfy a test plan.

## Machine-readable policy

The executable source of truth lives in:

`src/pyschedulekit/infrastructure/persistence_versions.py`

with `V1_POSTGRES_ROLLING_UPGRADE_POLICY` and
`V1_POSTGRES_ROLLING_UPGRADE_GATES`.

The contract is:

```text
current schema overlap
    same-contract workers qualified

adjacent release overlap
    explicit release-pair qualification required

schema-changing upgrade default
    drain workers before migration

default upgrade order
    backup → drain → migrate → deploy → verify → resume

overlap-safe schema change
    expand → migrate → contract required

contract DDL while old workers overlap
    forbidden

writer/reader overlap
    bidirectional readability required

unknown future schema
    fail closed until an explicit migration exists

PostgreSQL server major upgrade
    drain and perform outside PyScheduleKit
```

## “Same-contract workers” means exactly this

V1-02.E uses two independently created `PostgresUnitOfWorkFactory` instances representing
two scheduler workers using the same PyScheduleKit persistence contract.

The live tests prove that:

1. worker A can write a Schedule;
2. worker B can load and update it;
3. worker A can then observe worker B's committed state;
4. both operate under the same schema v1 and codec contract.

This is a **same-contract overlap guarantee**.

It is not evidence that arbitrary historical and future package releases may overlap.

## Adjacent release pair rule

For a future deployment from release N to release N+1, overlap is supported only if that
specific release pair has executable evidence.

The qualification must prove at minimum:

- both binaries accept the database schema visible during overlap;
- N can read every durable representation N+1 may write during overlap;
- N+1 can read every representation N may still write;
- coordination rows have compatible ownership/fencing semantics;
- stale owners remain rejected after takeover;
- transaction/constraint behavior remains compatible;
- PostgreSQL 16/17/18 live CI is green for the overlap scenario.

Without this evidence:

```text
N workers
   ↓ drain completely
schema/data migration
   ↓
N+1 workers
```

is the required deployment model.

## Why bidirectional readability is required

Forward readability alone is insufficient during a rolling deployment.

If N+1 can read N data but N cannot read data newly written by N+1, then a surviving N worker
can fail after N+1 begins writing.

Therefore overlap requires:

```text
N reads N writes       ✅
N+1 reads N writes     ✅
N reads N+1 writes     ✅
N+1 reads N+1 writes   ✅
```

for every persisted representation that may be touched during the overlap window.

This rule applies to:

- PostgreSQL physical schema;
- ScheduleDefinition JSON;
- Trigger envelopes;
- generic SQL value codecs;
- durable coordination rows;
- any future versioned PostgreSQL-specific representation.

## Schema evolution model

A schema-changing release has two possible deployment modes.

### Default: drained migration

This is the baseline contract:

```text
backup
  ↓
drain all scheduler workers
  ↓
apply explicit forward migration
  ↓
deploy new PyScheduleKit workers
  ↓
bootstrap / schema verification
  ↓
readiness + reconciliation
  ↓
resume traffic
```

This path does not require old/new worker overlap.

### Explicitly overlap-safe migration

Zero-downtime overlap requires an expand/migrate/contract strategy.

```text
EXPAND
add structures tolerated by old workers
        ↓
MIGRATE
backfill / dual-compatible representation
        ↓
DEPLOY
old + new workers overlap only with explicit pair evidence
        ↓
DRAIN OLD
no N workers remain
        ↓
CONTRACT
remove obsolete structures only after overlap has ended
```

Contract/destructive DDL is forbidden while workers that depend on the old shape may still be
running.

## Concurrent bootstrap guarantee

`initialize_postgres_schema()` uses a project-specific transaction-scoped PostgreSQL
advisory lock.

V1-02.E now exercises four concurrent schema-v1 initializers against one empty database.

Required result:

- all initializers complete successfully;
- exactly one metadata version is established;
- the complete schema exists;
- no session-level advisory lock leaks after transaction completion.

This protects multi-replica startup where several workers race to initialize an empty
database.

## Fencing during overlap

Rolling deployment safety depends on stale workers being unable to act after ownership
transfer.

V1-02.E explicitly qualifies this sequence on PostgreSQL:

```text
worker-old acquires lease
generation = 1
        ↓
lease remains active
worker-new acquisition rejected
        ↓
lease expires
        ↓
worker-new takes over
generation = 2
        ↓
worker-old stale release rejected
        ↓
worker-new release succeeds
```

The generation must increase monotonically.

A release that changes lease/claim ownership semantics cannot be declared overlap-safe without
re-running equivalent fencing evidence.

## Unknown future schemas remain fail-closed

Current runtime schema version is v1.

V1-02.E verifies that if metadata advertises v2 before PyScheduleKit contains an explicit v2
migration:

- factory construction fails immediately;
- existing durable rows are not mutated;
- the runtime does not guess or silently rewrite the database.

This is a core safety boundary for rolling upgrades.

## PostgreSQL server-major upgrades

PostgreSQL 16, 17 and 18 are supported server majors, but changing the server major is a
database infrastructure operation, not a PyScheduleKit rolling schema migration.

The supported procedure remains:

```text
backup → drain → PostgreSQL major upgrade → PyScheduleKit verify → readiness → resume
```

PyScheduleKit does not automate `pg_upgrade`, logical migration, dump/restore or managed
service major-version workflows.

## Live executable evidence

Canonical test:

`tests/integration/postgres/test_v1_postgres_rolling_upgrade.py`

Architecture policy test:

`tests/architecture/test_v1_postgres_rolling_upgrade_policy.py`

The PostgreSQL workflow runs the live integration suite against:

```text
PostgreSQL 16
PostgreSQL 17
PostgreSQL 18
```

The V1-02.E gate set is:

```text
concurrent-schema-bootstrap
same-contract-cross-worker-read-write
fencing-generation-monotonicity
stale-owner-rejection-after-takeover
unknown-future-schema-fail-closed
postgres-16-17-18-live-qualification
```

## Rules for the first future schema v2

A PostgreSQL schema v2 change is not complete unless the same change provides:

1. explicit v1→v2 migration code;
2. immutable migration input evidence where practical;
3. PostgreSQL 16/17/18 forward-migration tests;
4. partial/failure-state tests;
5. backup and recovery instructions;
6. a declared rollout mode:
   - drained only; or
   - explicit N/N+1 overlap;
7. if overlap is claimed, bidirectional reader/writer compatibility tests;
8. fencing/lease takeover tests with N and N+1 behavior;
9. delayed contract DDL until old workers are gone;
10. V1-02 persistence-floor invariants preserved.

Schema v1 remains the frozen readable floor throughout PyScheduleKit 1.x.

## What is not promised

V1-02.E does **not** promise:

- downgrade readability from an arbitrary new schema to an older binary;
- arbitrary overlap between any two 1.x releases;
- overlap with pre-1.0 PostgreSQL implementations;
- automatic PostgreSQL server-major upgrades;
- SQLite→PostgreSQL migration;
- destructive schema changes without drain/qualification;
- zero-downtime schema evolution by default.

## V1-02 status

```text
V1-02.A  Persistence Version Floor & Policy          COMPLETE
V1-02.B  Immutable Golden Compatibility Fixtures     COMPLETE
V1-02.C  SQLite Forward Migration Qualification      COMPLETE
V1-02.D  Codec Migration & Semantic Equivalence      COMPLETE
V1-02.E  PostgreSQL Evolution / Rolling Upgrade      COMPLETE
V1-02.F  Backup / Rollback / Operations Contract     COMPLETE
V1-02.G  Final Persistence Compatibility Review      NEXT
```

---

**Status:** V1-02.E complete once architecture, CI, Distribution Qualification and live
PostgreSQL 16/17/18 qualification are green. Next: **V1-02.G — Final Persistence Compatibility Review**.
