# V1-02.C — SQLite Forward Migration Qualification

**Scope:** physical SQLite database compatibility from every supported historical runtime
schema into the current schema v8.

**Runtime scheduling semantics changed:** no  
**SQLite writer version changed:** no  
**Package version changed:** no

## Objective

V1-02.A froze the SQLite 1.x read floor at schema v1.

V1-02.C converts that promise into physical database evidence. It commits one real SQLite
database fixture for every historical schema version v1 through v7 and proves that the
current runtime can migrate each one to v8 while preserving durable state.

The compatibility path under qualification is:

```text
v1 → v2 → v3 → v4 → v5 → v6 → v7 → v8
v2 → v3 → v4 → v5 → v6 → v7 → v8
v3 → v4 → v5 → v6 → v7 → v8
v4 → v5 → v6 → v7 → v8
v5 → v6 → v7 → v8
v6 → v7 → v8
v7 → v8
```

Every supported entry point is therefore executable evidence, not an inferred transitive
claim.

## Physical fixture set

Fixtures live under:

`tests/fixtures/persistence/v1/sqlite/`

and are compressed as `.db.xz`.

After decompression each file is a real SQLite database.

```text
sqlite_schema_v1.db.xz
sqlite_schema_v2.db.xz
sqlite_schema_v3.db.xz
sqlite_schema_v4.db.xz
sqlite_schema_v5.db.xz
sqlite_schema_v6.db.xz
sqlite_schema_v7.db.xz
```

XZ is only storage compression for Git. It is not part of the persistence contract.

Each fixture has:

- compressed byte size and SHA-256;
- decompressed SQLite byte size and SHA-256;
- declared historical schema version;
- representative durable data.

## Representative durable graph

Every fixture contains the same core graph:

```text
Schedule
  └── ExecutionRequest
       └── Execution (SUCCESS)
            └── Attempt (SUCCESS)
```

The persisted Schedule definition intentionally uses the released ScheduleDefinition v1
format so the database migration test also crosses the historical serialized-definition
boundary.

Feature rows are added only once they exist in that schema generation:

```text
v1  core graph
v2  core graph + hardened FK/CHECK/UNIQUE schema
v3  + published outbox message
v4  + released execution claim
v5  + released schedule admission lock
v6  + claim/lock fencing generations
v7  + released schedule materialization lease
```

This prevents a false migration qualification based on empty databases.

## Historical structure checks

Before migration the tests assert the physical shape expected for the declared version.

Examples:

- v1/v2 contain only the four core tables plus schema metadata;
- v3 contains outbox;
- v4 contains execution claims without `generation`;
- v5 contains admission locks without `generation`;
- v6 contains `generation` on claims and admission locks;
- v7 contains materialization leases;
- none of v1-v7 contains `executions.completed_at`.

The fixture therefore cannot silently claim to be v4 while physically containing v7
structures.

## Migration execution

Tests never mutate the committed fixture in place.

For each version they:

1. read the compressed fixture;
2. verify its compressed SHA-256;
3. decompress it;
4. verify the raw SQLite SHA-256;
5. write a temporary copy;
6. inspect the historical schema;
7. instantiate `SqliteUnitOfWorkFactory`;
8. let the production schema initializer execute the normal forward migration chain;
9. reopen the migrated database for structural and semantic verification.

No test-only migration implementation exists.

## Post-migration v8 guarantees

Every migrated database must satisfy:

- schema metadata reports v8;
- `PRAGMA integrity_check` returns `ok`;
- `PRAGMA foreign_key_check` returns no violations;
- all current v8 tables exist;
- all current v8 indexes exist;
- core durable rows remain present;
- the current repositories can reconstruct Schedule, Request, Execution and Attempt;
- the released ScheduleDefinition v1 payload is still semantically readable;
- terminal Execution state/result remains SUCCESS;
- `executions.completed_at` is backfilled from historical result JSON.

## Feature-row preservation

Migration also verifies historical feature rows.

### Outbox

For source v3+:

- the published outbox row survives;
- state remains `published`;
- publish attempt count remains unchanged.

For v1/v2 the newly created v8 outbox table is empty.

### Execution claims

For source v4+ the released claim survives.

Generation behavior is version-sensitive:

```text
v4/v5 source  → v6 migration default generation = 1
v6/v7 source  → explicit historical generation = 3 preserved
```

### Admission locks

For source v5+ the released admission lock survives.

```text
v5 source     → v6 migration default generation = 1
v6/v7 source  → explicit historical generation = 4 preserved
```

### Materialization leases

For source v7 the released materialization lease survives with generation 5.

For older source schemas the v8 table is created empty.

## Retention backfill

Schema v8 adds `executions.completed_at`.

The v7→v8 migration derives this value from the durable execution result payload.

Every fixture contains a terminal Execution with:

`2026-01-01T10:05:00+00:00`

and the final database must contain that exact timestamp in `executions.completed_at`.

This explicitly protects the semantic data migration, not just the column creation.

## Fixture immutability

`tests/fixtures/persistence/v1/sqlite/manifest.json` records both compressed and raw hashes.

`tests/compatibility/test_v1_sqlite_forward_migrations.py` independently freezes the same
inventory and hashes.

A changed fixture therefore requires an explicit test change and review.

Merged historical fixtures are append-only. A future schema v9 must add new evidence; it
must not rewrite v1-v7 history.

## Relationship to existing migration tests

Existing integration tests remain valuable:

- v1 synthetic migration coverage;
- v2 outbox migration;
- v6 materialization migration;
- v7 retention backfill.

V1-02.C adds the missing stable-release layer:

- committed physical inputs;
- immutable hashes;
- every historical entry point v1-v7;
- common semantic-preservation assertions;
- direct mapping to the frozen 1.x persistence floor.

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

## Deliberate boundary

V1-02.C does not:

- change SQLite schema v8;
- introduce schema v9;
- guarantee downgrade readability;
- qualify simultaneous old/new workers during a schema transition;
- qualify PostgreSQL schema evolution;
- replace V1-02.D codec semantic-equivalence testing;
- change package version, tag or publication state.

---

**Status:** V1-02.C physical migration evidence is qualified and V1-02.D semantic codec
equivalence is complete. Next: **V1-02.G — Final Persistence Compatibility Review**.
