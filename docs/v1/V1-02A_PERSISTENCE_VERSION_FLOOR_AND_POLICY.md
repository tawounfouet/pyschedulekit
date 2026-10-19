# V1-02.A — Persistence Version Floor & Policy

**Scope:** minimum readable persisted versions and evolution rules for the PyScheduleKit 1.x
line.

**Runtime scheduling behavior changed:** no  
**Persistence bytes changed:** no  
**Package version changed:** no

## Objective

V1-02.A turns existing versioned persistence mechanisms into an explicit compatibility
promise.

Before this lot, PyScheduleKit already had forward SQLite migrations, strict JSON codecs,
fail-closed future-version handling and a qualified PostgreSQL schema. What was missing was
the long-term rule that answers:

> Which persisted versions must every PyScheduleKit 1.x release continue to read?

The machine-readable source of truth is
`src/pyschedulekit/infrastructure/persistence_versions.py`.

## Frozen 1.x read floors

The following minimum versions are frozen for the full 1.x major line:

| Persistence surface | 1.x minimum readable version | Current writer |
|---|---:|---:|
| SQLite runtime schema | 1 | 8 |
| PostgreSQL runtime schema | 1 | 1 |
| generic SQL value codec | 1 | 1 |
| ScheduleDefinition codec | 1 | 3 |
| versioned Trigger envelope | 1 | 1 |
| BusinessCalendar value codec | 1 | 1 |
| BusinessCalendar collection codec | 1 | 1 |
| SQLite calendar-provider schema | 1 | 1 |

Raising any of these read floors inside 1.x is a breaking compatibility change.

## SQLite runtime schema

The current SQLite runtime writer is schema v8.

The supported historical chain is:

```text
v1 → v2 → v3 → v4 → v5 → v6 → v7 → v8
```

PyScheduleKit 1.x therefore commits to accepting a valid SQLite runtime database whose
metadata reports any schema version from v1 through the then-current writer version, provided
an explicit migration path exists in that release.

The floor is v1.

Future unknown versions fail closed.

A migration may add intermediate schema versions during 1.x, but it may not remove the
ability to start from v1 unless a future major version changes the persistence contract.

## PostgreSQL runtime schema

The current PostgreSQL runtime schema is v1.

The 1.x floor is therefore v1.

At the time of this decision there is no v1→v2 PostgreSQL migration because no schema v2
exists. A future schema bump is only compatible if the same release supplies and qualifies a
forward path from every supported prior schema version down to the frozen v1 floor.

The PostgreSQL server-version support matrix is a separate platform-support concern. The
schema floor describes PyScheduleKit-owned durable data, not PostgreSQL server binaries.

## Generic SQL value codec

The SQL adapters persist multiple value snapshots through the shared generic codec, including
retry/concurrency policies and execution/attempt results.

That format uses:

```text
version = 1
```

Although this codec was not called out separately in the original V1-00 table, it is part of
the actual durable row contract and is therefore explicitly covered by V1-02.

Its 1.x read floor is v1.

## ScheduleDefinition codec

The current writer emits ScheduleDefinition codec v3.

The reader already supports:

```text
v1  original definition, no calendar binding
v2  calendar binding, legacy flat Trigger representation
v3  current definition with versioned Trigger envelope
```

The 1.x floor is v1.

This means v1 and v2 payloads are not merely migration-test artifacts: once 1.0.0 is
activated they become long-term readable compatibility inputs for the entire 1.x line.

Writers continue to emit only the current format.

## Trigger envelope codec

Current versioned Trigger envelopes use:

```text
schema_version = 1
```

The 1.x floor for versioned Trigger envelopes is v1.

Legacy ScheduleDefinition v1/v2 payloads predate independent Trigger envelope versioning.
Their flat Trigger representation remains supported through the ScheduleDefinition v1/v2
compatibility promise, not by pretending those historical payloads were Trigger envelope
v0.

Unknown future Trigger versions fail closed.

Nested composite Trigger children obey the same rule: every versioned child must use a
supported Trigger envelope version.

## Calendar codecs

BusinessCalendar persistence has two JSON layers:

- one calendar value;
- one deterministic collection of calendar values.

Both currently use schema version 1 and both have a frozen 1.x read floor of v1.

The SQLite calendar provider also has its own isolated database schema at v1. Its read floor
is independently frozen at v1.

The calendar-provider schema may share a SQLite file with the Scheduler runtime schema, but
the two version domains remain independent.

## Compatibility rules

The machine-readable policy records seven governing rules.

### Read-floor lifetime

```text
frozen-through-1.x
```

Once 1.0.0 is activated, supported persisted versions at or above the frozen floor remain
readable throughout the 1.x major line.

### Future versions

```text
fail-closed
```

PyScheduleKit must reject a persisted version it does not understand. It must not guess,
silently coerce, or downgrade unknown future data.

### Writer evolution

```text
forward-migration-and-golden-evidence-required
```

A writer-version increase is not complete until the same change supplies executable forward
migration evidence and updates the immutable compatibility fixtures required by V1-02.B.

### Downgrade readability

```text
not-guaranteed
```

PyScheduleKit guarantees forward compatibility from supported historical data into newer
1.x releases. It does not guarantee that an older PyScheduleKit release can reopen storage
after a newer release has upgraded it.

This is why backup and rollout discipline matter.

### Mixed-version workers

```text
explicit-overlap-qualification-required
```

A rolling deployment with old and new scheduler workers concurrently touching the same
durable store is not assumed safe merely because both versions are individually supported.

Mixed-version operation is supported only when the relevant schema/codec transition has an
explicit overlap test and documented rollout contract.

Without that evidence, workers must be drained before a format-changing upgrade.

### Backup prerequisite

```text
required-before-format-changing-upgrade
```

Any production upgrade that may mutate durable storage requires a verified backup or
equivalent restorable snapshot before migration.

V1-02.F will turn this policy into the operational backup/rollback runbook.

### Cross-adapter migration

```text
unsupported
```

SQLite→PostgreSQL, PostgreSQL→SQLite, or other physical cross-adapter data migration is not a
1.x compatibility guarantee.

Adapter parity guarantees observable persistence semantics. It does not imply a first-party
data-transfer tool or byte-compatible schemas.

## What counts as a compatible persistence change

Examples that may be compatible inside 1.x when fully qualified:

- adding a new SQLite schema version with a forward path from every supported prior version;
- adding an optional field to a current writer format while older persisted payloads remain
  readable;
- adding a new Trigger kind with its own schema version;
- adding a new PostgreSQL schema version with a tested migration from the v1 floor;
- extending calendar persistence while preserving v1 reads.

Examples that are breaking inside 1.x:

- refusing to open a valid SQLite v1 database;
- refusing to decode a valid ScheduleDefinition v1/v2 solely because the writer is now v3+;
- changing a Trigger v1 payload meaning incompatibly;
- changing a calendar v1 meaning incompatibly;
- raising the PostgreSQL schema floor above v1;
- silently reinterpreting an unknown future version.

## Central version source

The internal dependency-neutral module records current writers and V1 floors:

```text
SQLITE_RUNTIME_SCHEMA_VERSION       = 8
POSTGRES_RUNTIME_SCHEMA_VERSION     = 1
SQL_VALUE_CODEC_VERSION             = 1
SCHEDULE_DEFINITION_CODEC_VERSION   = 3
TRIGGER_CODEC_VERSION               = 1
CALENDAR_VALUE_CODEC_VERSION        = 1
CALENDAR_COLLECTION_CODEC_VERSION   = 1
SQLITE_CALENDAR_SCHEMA_VERSION      = 1
```

SQLite, PostgreSQL, SQL codecs and calendar adapters source their runtime version constants
from this module so documentation/tests cannot drift from implementation silently.

## Executable evidence

`tests/architecture/test_v1_persistence_compatibility_policy.py` verifies:

- exact 1.x read floors;
- exact current writer versions;
- exact evolution rules;
- runtime SQLite/SQL/calendar constants match the central contract;
- every current writer is at or above its frozen floor.

PostgreSQL uses the same dependency-neutral central version constant while preserving its
optional dependency boundary.

## V1-02 delivery sequence

V1-02 is intentionally split so policy is fixed before fixtures and migration evidence:

```text
V1-02.A  Persistence Version Floor & Policy          COMPLETE
V1-02.B  Immutable Golden Compatibility Fixtures     COMPLETE
V1-02.C  SQLite Forward Migration Qualification      COMPLETE
V1-02.D  Codec Migration & Semantic Equivalence      NEXT
V1-02.E  PostgreSQL Evolution / Rolling Upgrade      PLANNED
V1-02.F  Backup / Rollback / Operations Contract     PLANNED
V1-02.G  Final Persistence Compatibility Review      PLANNED
```

## Deliberate boundary

V1-02.A does not yet:

- commit immutable historical golden fixture files;
- prove every SQLite floor migration from fixture bytes;
- expand semantic equivalence testing across all frozen codecs;
- implement a PostgreSQL schema v2;
- claim mixed-version rolling upgrades are currently safe;
- add a cross-adapter migration tool;
- change the package version or publish anything.

Those are addressed by the remaining V1-02 lots where applicable.

---

**Status:** V1-02.A persistence floors remain frozen. V1-02.B and V1-02.C are complete;
the active persistence step is **V1-02.D — Codec Migration & Semantic Equivalence**.
