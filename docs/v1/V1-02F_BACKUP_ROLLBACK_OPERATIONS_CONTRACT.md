# V1-02.F — Backup / Rollback / Operations Contract

**Scope:** persistence backup, restore rehearsal, rollback boundary and operational GO/ABORT
criteria for the PyScheduleKit 1.x line.

**Runtime persistence semantics changed:** no  
**Database schema versions changed:** no  
**Package version changed:** no

## Objective

V1-02.A through V1-02.E freeze the persistence floors, immutable historical evidence, SQLite
forward migrations, codec semantic equivalence and PostgreSQL rolling-upgrade boundary.

V1-02.F answers the operational question that remains:

> If a persistence-affecting upgrade goes wrong, what exact evidence must exist before GO,
> what constitutes ABORT, and how is a known-good state restored safely?

The answer is deliberately conservative.

~~~text
backup → verify → migrate → verify → resume
~~~

Rollback means:

~~~text
stop writes
  ↓
drain
  ↓
restore-known-good-backup
  ↓
deploy compatible binary
  ↓
verify
  ↓
resume
~~~

There is **no in-place downgrade** guarantee.

## Machine-readable operations policy

The executable policy is stored in
'src/pyschedulekit/infrastructure/persistence_versions.py'.

'V1_PERSISTENCE_OPERATIONS_POLICY' freezes these rules:

~~~text
backup-before-format-change
    required

backup-integrity-verification
    required

restore-rehearsal-before-release
    required

rollback-mode
    restore-known-good-backup-not-in-place-downgrade

migration-interruption
    transactional-step-or-fail-closed

sqlite-backup
    sqlite-backup-api-or-consistent-offline-copy

postgres-backup
    native-postgres-backup-required

postgres-restore-rehearsal
    pg-dump-pg-restore-live-ci

post-restore-verification
    schema-integrity-domain-smoke-required

go-no-go
    explicit-preflight-and-postflight-gates

rpo-rto
    application-owned
~~~

## Operations gate set

V1-02.F requires executable evidence for:

~~~text
backup-artifact-created
backup-integrity-verified
restore-rehearsal-passed
sqlite-interrupted-migration-rollback
post-restore-schema-verification
post-restore-domain-smoke
postgres-16-17-18-backup-restore-rehearsal
explicit-go-abort-criteria
~~~

## GO criteria

A persistence-affecting upgrade may proceed only when all preflight conditions are satisfied.

### Preflight GO criteria

- current persistence version is known and supported;
- target migration path is explicit;
- required workers are drained when the rollout contract demands it;
- a backup artifact exists;
- the backup is non-empty;
- backup integrity has been verified;
- a checksum or equivalent identity has been recorded;
- restore rehearsal has passed for the engine/version in scope;
- the compatible rollback binary/version is known;
- the operator knows who owns the GO/ABORT decision;
- the pre-upgrade backup will be retained until postflight acceptance.

If any preflight criterion fails:

~~~text
ABORT
~~~

No migration starts.

### Postflight GO criteria

Traffic resumes only when:

- schema/version verification succeeds;
- engine integrity checks succeed;
- representative durable domain state is readable;
- coordination/fencing rows remain structurally valid;
- readiness/reconciliation succeeds;
- no unknown future persistence version is observed;
- no partial migration state remains.

If any postflight criterion fails:

~~~text
ABORT
        ↓
restore known-good backup
~~~

## SQLite backup contract

For a live SQLite database, the preferred qualified mechanism is Python's SQLite online backup
API:

~~~python
with sqlite3.connect(source) as source_connection:
    with sqlite3.connect(backup) as backup_connection:
        source_connection.backup(backup_connection)
~~~

A consistent offline copy is acceptable only when writers are stopped and SQLite
journal/WAL consistency is handled correctly.

Copying only the main database file from an actively written WAL database is not qualified.

## SQLite current-schema restore rehearsal

V1-02.F creates a current SQLite v8 database through 'SqliteUnitOfWorkFactory', writes a
real Schedule, produces an online backup, verifies:

~~~text
artifact exists
artifact non-empty
PRAGMA integrity_check == ok
schema version == v8
~~~

The live database is then mutated.

The backup is restored to a separate path and reopened through
'SqliteUnitOfWorkFactory'.

Required result:

- the pre-mutation Schedule is present;
- its state remains ACTIVE;
- its next-run semantics remain exact.

This proves the backup is not merely readable bytes; it restores domain state.

## SQLite pre-upgrade rollback boundary

The immutable V1-02.C physical schema-v7 fixture is reused as pre-upgrade evidence.

V1-02.F:

1. inflates the v7 database;
2. verifies v7 integrity;
3. creates an online backup;
4. migrates the live copy through the production initializer to v8;
5. verifies the live copy is v8 and healthy;
6. restores the backup to a separate database;
7. proves the restored copy remains a healthy v7 database with durable Schedule/Execution data.

This demonstrates the rollback boundary:

~~~text
known-good v7 backup
        │
        ├── live copy migrates → v8
        │
        └── rollback artifact remains → v7
~~~

Rollback does not mean converting v8 back to v7.

## SQLite interrupted-migration atomicity

V1-02.F actively injects a failure during the production v7→v8 migration.

The failure occurs after executing the first DDL action:

~~~sql
ALTER TABLE executions ADD COLUMN completed_at TEXT;
~~~

and before the migration can complete.

Because the migration step is transactional, the required result after the forced exception is:

~~~text
pyschedulekit_schema.version == 7
completed_at column absent
PRAGMA integrity_check == ok
~~~

A partially committed schema would fail this gate.

This is stronger than documenting rollback behavior: the CI executes the interruption.

## PostgreSQL backup contract

PostgreSQL backup must use PostgreSQL-native or provider-native mechanisms.

V1-02.F live CI qualifies one concrete portable baseline:

~~~text
pg_dump --format custom
        ↓
verify dump inventory + SHA-256
        ↓
destroy public schema
        ↓
pg_restore
        ↓
reopen PostgresUnitOfWorkFactory
        ↓
read durable Schedule probe
~~~

Production applications may instead use:

- physical PostgreSQL backups;
- managed-service snapshots;
- PITR;
- organization-approved backup platforms.

The requirement is restoreability, not one mandated vendor workflow.

## Matching PostgreSQL client/server qualification

The rehearsal deliberately executes 'pg_dump' and 'pg_restore' **inside the same PostgreSQL
service image** used by the CI matrix.

That avoids accidentally qualifying:

~~~text
old pg_dump client → newer PostgreSQL server
~~~

as if it were a supported operational contract.

Each supported server major therefore uses its matching native tools.

## PostgreSQL 16/17/18 restore rehearsal

For each supported major:

~~~text
PostgreSQL 16
PostgreSQL 17
PostgreSQL 18
~~~

the CI performs:

1. current schema bootstrap;
2. durable Schedule write through the public PostgreSQL adapter;
3. custom-format pg_dump;
4. non-empty artifact verification;
5. SHA-256 calculation;
6. pg_restore --list inventory verification;
7. destructive removal of the live public schema;
8. pg_restore;
9. new PostgresUnitOfWorkFactory construction;
10. durable Schedule semantic verification.

This is a true restore rehearsal, not a documentation-only backup command.

## Migration failure versus rollback

Two distinct failure classes are intentionally separated.

### Failure before migration commit

If a migration step is transactionally rolled back:

~~~text
old schema remains authoritative
~~~

The upgrade is aborted and diagnostics are preserved.

### Failure after migration commit

If postflight verification fails after the new schema/format is committed:

~~~text
do not attempt ad-hoc inverse DDL
        ↓
drain new workers
        ↓
restore pre-upgrade backup
        ↓
deploy compatible previous binary
        ↓
verify
~~~

This avoids pretending downgrade readability is guaranteed.

## Explicit ABORT criteria

The migration/change window must abort if any of the following occurs:

- backup artifact missing or empty;
- backup integrity check fails;
- checksum/inventory cannot be verified;
- restore rehearsal fails;
- required workers cannot be drained;
- current schema version is unexpected;
- migration raises or leaves a partial state;
- post-migration integrity fails;
- durable domain smoke verification fails;
- readiness/reconciliation fails;
- unknown future persistence version appears;
- rollback compatibility is unknown.

## RPO/RTO boundary

PyScheduleKit guarantees correctness-oriented evidence.

It does not choose an application's:

- backup frequency;
- retention period;
- replication topology;
- PITR window;
- RPO;
- RTO;
- encryption policy;
- off-site durability;
- backup access policy;
- on-call/operator staffing.

Those remain application-owned.

## Operational runbook

The detailed operator-facing procedure is:

'docs/operations/PERSISTENCE_BACKUP_RESTORE_RUNBOOK.md'

It contains concrete SQLite and PostgreSQL commands and the complete GO/ABORT flow.

## Executable evidence

### Architecture/policy

'tests/architecture/test_v1_persistence_operations_policy.py'

### SQLite

'tests/compatibility/test_v1_sqlite_backup_restore_operations.py'

### PostgreSQL

'scripts/qualification/postgres_backup_restore_probe.py'

'scripts/qualification/postgres_backup_restore_rehearsal.sh'

'.github/workflows/postgres.yml'

The PostgreSQL workflow executes the restore rehearsal on 16, 17 and 18.

## V1-02 status

~~~text
V1-02.A  Persistence Version Floor & Policy          COMPLETE
V1-02.B  Immutable Golden Compatibility Fixtures     COMPLETE
V1-02.C  SQLite Forward Migration Qualification      COMPLETE
V1-02.D  Codec Migration & Semantic Equivalence      COMPLETE
V1-02.E  PostgreSQL Evolution / Rolling Upgrade      COMPLETE
V1-02.F  Backup / Rollback / Operations Contract     COMPLETE
V1-02.G  Final Persistence Compatibility Review      NEXT
~~~

## Deliberate boundary

V1-02.F does not:

- add a public backup API;
- automate production backups;
- set application RPO/RTO;
- implement in-place downgrade;
- add PostgreSQL schema v2;
- introduce SQLite→PostgreSQL migration;
- change package version, tag or publication state.

Those are outside this lot.

---

**Status:** V1-02.F complete once CI, Distribution Qualification, SQLite operational tests and
PostgreSQL 16/17/18 backup/restore rehearsals are green. Next:
**V1-02.G — Final Persistence Compatibility Review**.
