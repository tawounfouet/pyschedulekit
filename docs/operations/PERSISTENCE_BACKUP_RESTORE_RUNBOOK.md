# Persistence Backup / Restore Runbook

This runbook defines the operational procedure for PyScheduleKit persistence changes.

It applies to:

- SQLite runtime persistence;
- PostgreSQL runtime persistence;
- schema-changing upgrades;
- persisted-format changes that can affect rollback safety.

It does **not** define application-specific RPO/RTO targets. Those remain application-owned.

## Core rule

A format-changing upgrade follows:

```text
backup → verify → migrate → verify → resume
```

A rollback follows:

```text
abort new writes
  ↓
drain workers
  ↓
restore known-good pre-upgrade backup
  ↓
deploy binary compatible with that backup
  ↓
verify schema + domain state
  ↓
resume
```

There is no supported in-place downgrade mechanism.

## Preflight GO criteria

Proceed only when all of these are true:

- the current persistence version is known and supported;
- the target migration path is explicit;
- all required workers are drained when the upgrade contract requires it;
- a backup has been created;
- the backup artifact is non-empty;
- a cryptographic checksum has been recorded;
- backup integrity has been verified;
- a restore rehearsal for the target engine/version has passed;
- the rollback binary/version is known;
- the rollback operator and decision owner are known;
- capacity exists to retain the pre-upgrade backup until postflight acceptance.

If any item is false, the decision is **ABORT**.

## Postflight GO criteria

Resume scheduler traffic only when all of these are true:

- schema/version verification passes;
- database integrity checks pass;
- representative durable domain records are readable;
- coordination rows remain structurally valid;
- readiness/reconciliation completes as expected;
- no unknown future persistence version is observed;
- no partial migration state remains.

Otherwise: **ABORT and restore the known-good backup**.

# SQLite

## Backup method

For a live SQLite database, prefer the SQLite online backup API:

```python
import sqlite3

with sqlite3.connect("scheduler.db") as source:
    with sqlite3.connect("scheduler.backup.db") as destination:
        source.backup(destination)
```

This is the same `sqlite3.backup()` primitive used by the V1-02.F qualification suite.

A consistent offline copy is also acceptable when:

- all writers are stopped;
- WAL/journal state is handled correctly;
- the resulting copy is independently verified.

Do not copy only the main database file from an actively written WAL database and assume it
is a consistent backup.

## Backup verification

Run at minimum:

```sql
PRAGMA integrity_check;
SELECT version FROM pyschedulekit_schema;
```

Expected:

```text
integrity_check = ok
schema version = expected pre-upgrade version
```

Record a SHA-256 for the backup artifact when it is retained as an operational rollback point.

## Restore rehearsal

Restore the backup to a separate path first.

Verify:

1. `PRAGMA integrity_check = ok`;
2. expected `pyschedulekit_schema.version`;
3. expected durable Schedule/Execution graph rows;
4. PyScheduleKit can reopen the restored database when the running binary supports that schema.

The V1-02.F CI exercises a current-schema backup/restore and a pre-upgrade v7 snapshot.

## Interrupted migration

SQLite schema migrations are required to run transactionally per migration step.

V1-02.F injects a failure after the first DDL statement of the v7→v8 migration and requires:

- schema metadata remains v7;
- the v8 `completed_at` column is absent;
- `PRAGMA integrity_check = ok`.

A migration implementation that leaves a partially advanced schema after failure is not
releaseable.

# PostgreSQL

## Backup method

Use PostgreSQL-native backup tooling appropriate to your environment.

The CI rehearsal uses a custom-format logical backup:

```bash
pg_dump \
  --username postgres \
  --dbname pyschedulekit \
  --format custom \
  --no-owner \
  --no-privileges \
  > pyschedulekit.dump
```

Production environments may use:

- `pg_dump` / `pg_restore`;
- physical backups;
- managed-service snapshots;
- organization-approved PITR tooling.

The operational contract is not tied to one vendor, but the backup must be restorable.

## Backup verification

At minimum:

- artifact exists and is non-empty;
- checksum is recorded;
- dump inventory can be read;
- PyScheduleKit schema objects are present;
- restore rehearsal succeeds.

For custom dumps:

```bash
pg_restore --list pyschedulekit.dump
sha256sum pyschedulekit.dump
```

## Restore rehearsal

V1-02.F performs the following in live CI for PostgreSQL 16, 17 and 18:

1. create current PyScheduleKit schema;
2. write a real durable Schedule through `PostgresUnitOfWorkFactory`;
3. execute `pg_dump --format custom` using the matching PostgreSQL server image;
4. verify the dump inventory contains PyScheduleKit tables;
5. destroy the `public` schema;
6. restore with `pg_restore`;
7. reconstruct `PostgresUnitOfWorkFactory`;
8. read and validate the durable probe Schedule.

This qualifies restore mechanics, not your production RPO/RTO.

## PostgreSQL schema-changing upgrades

Unless a specific release pair has explicit V1-02.E overlap evidence:

```text
backup
  ↓
drain all workers
  ↓
migrate
  ↓
deploy new workers
  ↓
verify
  ↓
resume
```

Do not apply destructive/contract DDL while old workers may still be running.

# Rollback decision

Rollback is appropriate when postflight verification fails and the failure cannot be safely
corrected forward within the approved change window.

Examples:

- migration stops in an unexpected state;
- schema verification fails;
- restored/read domain semantics differ;
- readiness/reconciliation fails;
- new workers cannot operate safely;
- data integrity checks fail.

## Rollback sequence

1. stop admissions/new writes;
2. drain or stop new-version workers;
3. preserve diagnostics from the failed attempt;
4. restore the pre-upgrade known-good backup;
5. deploy the binary known to be compatible with that backup;
6. verify schema/integrity/domain state;
7. run readiness/reconciliation;
8. resume only after explicit GO.

## No in-place downgrade

PyScheduleKit does not promise that an older binary can read a newer schema or newer encoded
payloads.

Therefore:

```text
new schema → old binary
```

is not a rollback plan.

The rollback boundary is the pre-upgrade backup.

# RPO/RTO boundary

PyScheduleKit qualifies persistence correctness and restore mechanics.

Applications remain responsible for:

- backup frequency;
- retention;
- geographic replication;
- encryption;
- RPO;
- RTO;
- PITR retention;
- backup access control;
- off-site durability;
- restore staffing/on-call ownership.

# Evidence

Executable evidence:

- `tests/compatibility/test_v1_sqlite_backup_restore_operations.py`;
- `tests/architecture/test_v1_persistence_operations_policy.py`;
- `scripts/qualification/postgres_backup_restore_probe.py`;
- `scripts/qualification/postgres_backup_restore_rehearsal.sh`;
- PostgreSQL CI matrix 16/17/18.

Canonical V1 contract:

- `docs/v1/V1-02F_BACKUP_ROLLBACK_OPERATIONS_CONTRACT.md`.
