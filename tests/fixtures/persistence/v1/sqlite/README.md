# V1 SQLite Migration Fixtures

These are compressed **physical SQLite database files**, not SQL dumps.

Each `.db.xz` expands to one historical PyScheduleKit runtime database whose metadata
declares schema v1 through v7. The fixtures contain representative durable data rather than
empty schemas:

- one Schedule;
- one ExecutionRequest;
- one terminal Execution;
- one terminal Attempt;
- v3+: one published outbox message;
- v4+: one released execution claim;
- v5+: one released admission lock;
- v6+: persisted fencing generations;
- v7+: one released materialization lease.

## Why compressed?

SQLite files contain many zero-filled pages. XZ keeps the committed compatibility evidence
small while preserving the exact database bytes. Tests verify both the compressed SHA-256
and the decompressed raw SQLite SHA-256 before migration.

## Immutability

The fixtures are append-only compatibility evidence.

Tests never migrate these repository files in place. They:

1. verify compressed hash;
2. decompress to bytes;
3. verify raw SQLite hash;
4. write a copy under `tmp_path`;
5. inspect its declared historical schema;
6. run the real `SqliteUnitOfWorkFactory` migration chain on the copy;
7. verify schema v8 and semantic data preservation.

Do not regenerate a merged fixture to accommodate a future migration. If a new schema version
is introduced, add a new historical fixture and preserve all existing ones.

## Provenance

The fixture schema definitions correspond to the migration chain frozen at source baseline:

`3cd1787d8a3fb15bd790daad50d1432294b32f19`

That commit is the V1-02.B baseline immediately before physical SQLite migration
qualification began.
