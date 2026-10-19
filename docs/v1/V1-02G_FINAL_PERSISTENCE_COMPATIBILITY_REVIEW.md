# V1-02.G — Final Persistence Compatibility Review

**Review date:** 2026-10-19  
**Baseline:** V1-02.A through V1-02.F merged and green  
**Package version:** unchanged at pre-1.0 development identity  
**Release activation:** not part of this review

## Executive verdict

**V1-02 VERDICT: GO**

The persistence compatibility contract required for the PyScheduleKit 1.x line is now
complete enough to close V1-02.

That verdict is intentionally narrower than the product release verdict.

**Overall v1.0.0 verdict remains NO-GO** until V1-03, V1-04 and V1-05 are complete.

V1-02.G does not change a schema, codec, package version or public API. It audits the
persistence promise already built by V1-02.A through V1-02.F and verifies that every announced
1.x persistence guarantee has executable evidence.

## Review question

The final review asks:

> If PyScheduleKit 1.0 freezes the current persistence promise today, is that promise explicit,
> testable, operationally recoverable and narrow enough to remain credible throughout 1.x?

Answer: **yes**.

## 1.x persistence surface

The complete versioned persistence inventory is:

| Surface | 1.x readable floor | Current writer | Evidence |
|---|---:|---:|---|
| SQLite runtime schema | v1 | v8 | V1-02.A/B/C/F |
| PostgreSQL runtime schema | v1 | v1 | V1-02.A/E/F |
| ScheduleDefinition codec | v1 | v3 | V1-02.A/B/D |
| Trigger envelope codec | v1 | v1 | V1-02.A/D |
| Generic SQL value codec | v1 | v1 | V1-02.A/B/D |
| BusinessCalendar value codec | v1 | v1 | V1-02.A/B/D |
| Calendar collection codec | v1 | v1 | V1-02.A/B/D |
| SQLite calendar-provider schema | v1 | v1 | V1-02.A + CAL-05 qualification |

All currently versioned surfaces therefore have:

1. an explicit floor;
2. an explicit current writer;
3. fail-closed behavior for unknown future versions;
4. a documented future-evolution rule.

## V1-02.A — Version floor

Status: **PASS**

V1-02.A freezes every current persistence read floor at v1 for the lifetime of the 1.x line.

The machine-readable source of truth is:

`src/pyschedulekit/infrastructure/persistence_versions.py`

The final review confirms that the floor key set and writer key set are identical and that no
writer is below its frozen floor.

Current matrix:

```text
sqlite-runtime-schema          floor 1   writer 8
postgres-runtime-schema        floor 1   writer 1
schedule-definition-codec      floor 1   writer 3
trigger-envelope-codec         floor 1   writer 1
sql-value-codec                floor 1   writer 1
calendar-value-codec           floor 1   writer 1
calendar-collection-codec      floor 1   writer 1
sqlite-calendar-schema         floor 1   writer 1
```

## V1-02.B — Immutable compatibility fixtures

Status: **PASS**

The project now keeps immutable append-only historical serialization fixtures with SHA-256
protection.

They cover:

- public `v0.1.0a3` payloads;
- immutable final pre-1.0 payloads;
- ScheduleDefinition historical generations;
- SQL value payloads;
- BusinessCalendar value/collection payloads.

The guarantee is intentionally byte-level when the writer generation has not changed.

For a legacy generation that is migrated into a new writer generation, semantic equivalence
is handled by V1-02.D instead.

## V1-02.C — SQLite forward migrations

Status: **PASS**

Seven immutable physical SQLite databases cover runtime schemas v1 through v7.

Every historical entry point is migrated by the real production initializer to current v8:

```text
v1 → v8
v2 → v8
v3 → v8
v4 → v8
v5 → v8
v6 → v8
v7 → v8
```

The test suite verifies:

- compressed and raw fixture hashes;
- declared historical table/column shape;
- SQLite integrity;
- foreign-key integrity;
- complete target schema;
- Schedule / Request / Execution / Attempt preservation;
- outbox preservation where historically present;
- claim/admission-lock preservation;
- fencing-generation evolution;
- materialization-lease preservation;
- v7→v8 completed-at backfill semantics.

No unsupported downgrade promise is inferred from these forward-migration tests.

## V1-02.D — Codec semantic equivalence

Status: **PASS**

ScheduleDefinition is the only current codec with multiple readable generations.

The qualified migration matrix is:

```text
ScheduleDefinition v1 → v3
ScheduleDefinition v2 → v3
ScheduleDefinition v3 → v3
```

The suite proves both structural domain equality and observable scheduling behavior.

Qualified behavior includes:

- IntervalTrigger occurrence traces;
- BusinessDayTrigger calendar-aware traces;
- AnyOf(Date/Interval/Cron) composite traces;
- RetryEvaluator decisions;
- ConcurrencyEvaluator decisions;
- terminal Attempt/Execution result semantics;
- BusinessCalendar working-day decisions;
- deterministic calendar collection ordering.

This closes the gap between “old bytes still parse” and “old persisted meaning remains the
same”.

## V1-02.E — PostgreSQL evolution / rolling upgrade

Status: **PASS**

Current PostgreSQL schema is still v1, so no fictional v1→v2 migration was created.

The supported overlap guarantee is therefore deliberately narrow:

```text
same persistence contract
same PostgreSQL schema v1
multiple workers
→ qualified
```

Live CI on PostgreSQL 16, 17 and 18 proves:

- concurrent schema bootstrap;
- same-contract cross-worker read/write;
- monotonic fencing takeover;
- stale-owner rejection;
- unknown future schema fail-closed behavior.

Arbitrary N/N+1 overlap is **not** implied.

A future adjacent release pair must separately prove bidirectional readability for every
representation that may be written during overlap.

Default schema-changing deployment remains:

```text
backup → drain → migrate → deploy → verify → resume
```

An explicitly zero-downtime future schema evolution must use:

```text
expand → migrate → contract
```

with destructive/contract DDL delayed until old workers are gone.

## V1-02.F — Backup / rollback / operations

Status: **PASS**

The operations contract closes the recovery side of persistence compatibility.

SQLite evidence:

- live online backup using `sqlite3.backup()`;
- current v8 restore rehearsal;
- domain-state restoration after live database mutation;
- known-good v7 backup retained while live copy migrates to v8;
- forced failure during v7→v8 DDL;
- atomic rollback back to intact v7 after interruption.

PostgreSQL evidence on 16/17/18:

- real Schedule seed;
- matching-major native `pg_dump --format custom`;
- non-empty backup;
- SHA-256 recording;
- dump inventory verification;
- destructive removal of the live public schema;
- `pg_restore`;
- new `PostgresUnitOfWorkFactory`;
- durable Schedule semantic verification.

Rollback is frozen as:

```text
restore known-good pre-upgrade backup
```

not in-place inverse migration.

Application RPO/RTO remains outside the framework contract.

## Final compatibility rules

The complete 1.x persistence rules are:

```text
read floor
    frozen throughout 1.x

future unknown persisted versions
    fail closed

writer evolution
    explicit forward migration + golden evidence

downgrade readability
    not guaranteed

cross-adapter SQLite ↔ PostgreSQL migration
    unsupported unless separately implemented

mixed-version workers
    explicit overlap qualification required

schema-changing PostgreSQL rollout
    drain by default

overlap-safe PostgreSQL change
    expand/migrate/contract + bidirectional readability

backup before format-changing upgrade
    required

restore rehearsal before release
    required

rollback
    restore known-good backup

RPO/RTO
    application-owned
```

## Evidence map

| Guarantee | Executable evidence |
|---|---|
| frozen version floors | `tests/architecture/test_v1_persistence_contract.py` |
| immutable JSON fixtures | `tests/compatibility/test_v1_golden_persistence_fixtures.py` |
| SQLite v1→v8 migration | `tests/compatibility/test_v1_sqlite_forward_migrations.py` |
| codec semantic equivalence | `tests/compatibility/test_v1_codec_semantic_equivalence.py` |
| calendar provider schema fail-closed/reopen | `tests/unit/infrastructure/test_calendar_provider.py` |
| PostgreSQL overlap/fencing | `tests/integration/postgres/test_v1_postgres_rolling_upgrade.py` |
| PostgreSQL rollout policy | `tests/architecture/test_v1_postgres_rolling_upgrade_policy.py` |
| SQLite backup/restore + interrupted migration | `tests/compatibility/test_v1_sqlite_backup_restore_operations.py` |
| PostgreSQL backup/restore | `scripts/qualification/postgres_backup_restore_rehearsal.sh` |
| operations policy | `tests/architecture/test_v1_persistence_operations_policy.py` |
| final cross-contract review | `tests/architecture/test_v1_persistence_final_review.py` |

## V1-F04 closure

The original V1-00 finding was:

```text
V1-F04 — Persistence compatibility floor lacks a 1.x promise — P0
```

That finding is now **CLOSED**.

Closed by V1-02.A through V1-02.G:

- A freezes the minimum readable versions;
- B supplies immutable historical evidence;
- C qualifies SQLite forward migration;
- D qualifies semantic codec migration;
- E freezes PostgreSQL evolution/rolling rules;
- F proves backup/restore/rollback operations;
- G audits the complete promise and closes the finding.

No acceptance or waiver is required for V1-F04.

## Deliberate non-promises

The stable 1.x contract does not include:

- arbitrary downgrade readability;
- automatic SQLite→PostgreSQL migration;
- arbitrary old/new worker overlap;
- zero-downtime schema evolution by default;
- automatic production backups;
- application backup retention policy;
- RPO/RTO selection;
- PostgreSQL server-major upgrade automation;
- compatibility with unknown future schema/codec versions.

These exclusions are intentional parts of the stable contract, not missing implementation.

## Remaining release blockers

Persistence is no longer a V1 blocker after this review.

The remaining stabilization sequence is:

```text
V1-03  Platform, Warning and Security Gates    NEXT
V1-04  Consumer and Stable-Release Rehearsal   PLANNED
V1-05  Final GO/NO-GO and 1.0.0 Activation     PLANNED
```

V1-03 must address the still-open readiness findings around:

- Python 3.14 qualification;
- warning cleanliness;
- repository-owned dependency vulnerability auditing;
- CI action/runner deprecation policy.

V1-04 must address consumer preview and stable GitHub Release behavior.

V1-05 alone may activate the `1.0.0` version/tag after a final explicit GO.

## Final decision

```text
V1-02 Persistence Compatibility Contract    GO / COMPLETE
Overall PyScheduleKit v1.0.0                 NO-GO
Next                                         V1-03
```

No package version, tag, GitHub Release or PyPI publication is changed by V1-02.G.

---

**Status:** V1-02.G complete once the final-review architecture test passes the full CI and
distribution qualification. V1-02 then closes and **V1-03 — Platform, Warning and Security
Gates** becomes the active milestone.
