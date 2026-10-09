# CAL-04 — Persistence / Migration Parity

## Objective

Make calendar-aware Schedule definitions durable across framework upgrades without conflating
SQL schema migration with serialized domain-configuration migration.

The persistence specification distinguishes:

```text
Database Schema Migration
!=
Serialized Domain Configuration Migration
```

CAL-04 changes only the second layer.

## Starting point

Before CAL-04:

- Schedule-definition codec v1 represented the original definition without calendar binding;
- codec v2 added `CalendarSnapshotRef`;
- Date / Interval / Cron and later BusinessDay triggers were stored as flat JSON objects;
- trigger payloads had no independent schema version.

That made future trigger-format evolution hard to migrate explicitly.

## Current contract

CAL-04 writes Schedule definitions as codec **v3**.

The Trigger payload is independently versioned:

```json
{
  "version": 3,
  "payload": {
    "trigger": {
      "kind": "business_day",
      "schema_version": 1,
      "config": {
        "ordinal": -1,
        "hour": 18,
        "minute": 0,
        "ambiguous_time": "first",
        "nonexistent_time": "skip"
      }
    }
  }
}
```

The same envelope is used for all built-in trigger kinds.

## Read / write policy

```text
read supported legacy versions
normalize to current domain objects
write current version only
reject unsupported future versions
```

Supported Schedule-definition reads:

- v1 — original format, no calendar binding;
- v2 — calendar-aware definition with legacy flat Trigger payload;
- v3 — current definition with versioned Trigger envelope.

Current writes:

- Schedule-definition v3;
- Trigger schema v1.

## Legacy Trigger migration

Legacy v1/v2 trigger payload:

```json
{
  "kind": "interval",
  "every_seconds": 900,
  "anchor": "2026-01-01T10:00:00+00:00"
}
```

Current payload:

```json
{
  "kind": "interval",
  "schema_version": 1,
  "config": {
    "every_seconds": 900,
    "anchor": "2026-01-01T10:00:00+00:00"
  }
}
```

The decoder recognizes the legacy flat shape only for Schedule-definition v1/v2.
A v3 definition must contain a versioned Trigger payload.

## No silent downgrade

A future Schedule-definition version or Trigger schema version fails closed.

Examples:

```text
Schedule definition v4 on a v3 runtime
→ reject

Trigger schema v2 on a schema-v1 runtime
→ reject

Schedule definition v3 + unversioned flat trigger
→ reject
```

This prevents an older runtime from accepting a shape it cannot safely preserve.

## Semantic migration

Migration correctness is not only structural.

CAL-04 compares old and migrated Trigger semantics for a series of references:

```text
legacy trigger
+ reference
→ occurrence

migrated trigger
+ same reference
→ same occurrence
```

The conformance test includes timezone-sensitive Cron references.

## Live SQL parity

CAL-04 injects a real legacy v2 definition into current SQL rows for:

- SQLite;
- PostgreSQL.

The fixture includes:

- `BusinessDayTrigger`;
- exact `CalendarSnapshotRef`.

The repository must:

1. load the legacy row without changing the domain definition;
2. preserve the Schedule;
3. save it through the normal UnitOfWork contract;
4. rewrite `definition_json` as v3 / Trigger schema v1;
5. preserve the exact calendar reference and trigger semantics.

No SQL table or column migration is necessary.

## Explicit migration helper

`migrate_schedule_definition_json()` is an internal infrastructure helper:

```text
supported legacy JSON
→ decode current domain object
→ encode latest JSON
```

It is deliberately not part of the stable public API.

## Acceptance guarantees

1. v1 Schedule definitions remain readable;
2. v2 flat-trigger Schedule definitions remain readable;
3. v3 is the only Schedule-definition version written;
4. Trigger schema v1 is the only Trigger schema written;
5. legacy Date, Interval, Cron and BusinessDay triggers decode correctly;
6. v3 requires a versioned Trigger envelope;
7. future Schedule-definition versions fail closed;
8. future Trigger schema versions fail closed;
9. migration preserves Trigger occurrence semantics;
10. SQLite and PostgreSQL legacy rows load and upgrade on the next write;
11. calendar binding survives the migration exactly;
12. no database schema migration is introduced unnecessarily.

## Non-goals

CAL-04 does not add:

- new SQL columns or tables;
- destructive automatic migration;
- country holiday datasets;
- external CalendarProvider adapters;
- public migration CLI tooling.

External provider adapters belong to CAL-05.
