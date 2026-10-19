# V1-02.D — Codec Migration & Semantic Equivalence

**Scope:** persisted JSON compatibility across the frozen 1.x codec floor and current writer
versions.

**Runtime scheduling semantics changed:** no  
**Writer versions changed:** no  
**Package version changed:** no

## Objective

V1-02.A froze the 1.x persistence floor at v1. V1-02.B committed immutable historical JSON
fixtures. V1-02.C qualified the physical SQLite schema path from v1 through v7 into v8.

V1-02.D closes the remaining serialization question:

> When PyScheduleKit reads an older supported payload and rewrites it using the current
> codec, does the resulting object still mean and behave the same?

Byte identity is not the contract for a migrated payload. Semantic identity is.

The qualification model is therefore:

```text
historical bytes
      │
      ▼
legacy decoder
      │
      ▼
domain value A
      │
      ▼
current writer
      │
      ▼
current bytes
      │
      ▼
current decoder
      │
      ▼
domain value B

required:
A == B
observable behavior(A) == observable behavior(B)
```

## Current codec matrix

The executable source of writer versions remains
`src/pyschedulekit/infrastructure/persistence_versions.py`.

```text
generic SQL value codec          floor v1   writer v1
ScheduleDefinition codec         floor v1   writer v3
Trigger envelope codec           floor v1   writer v1
BusinessCalendar value codec     floor v1   writer v1
calendar collection codec        floor v1   writer v1
```

Only ScheduleDefinition currently has multiple supported generations.

This distinction matters. V1-02.D does **not** invent artificial v0/v2 histories for codecs
that have only ever had one supported generation.

## ScheduleDefinition migration qualification

The immutable fixture set gives three meaningful generations:

```text
released v0.1.0a3
ScheduleDefinition v1
  └─ flat IntervalTrigger

pre-1.0 checkpoint 945ec173…
ScheduleDefinition v2
  └─ calendar binding + flat BusinessDayTrigger

current pre-1.0 contract
ScheduleDefinition v3
  └─ versioned Trigger envelopes
     └─ AnyOf(Date, Interval, Cron)
```

V1-02.D qualifies:

```text
v1 → v3
v2 → v3
v3 → v3  (idempotence)
```

For each generation the compatibility suite requires:

- the historical fixture remains readable;
- `migrate_schedule_definition_json(...)` emits writer v3;
- the migrated Trigger envelope is writer v1;
- decoding before and after migration produces equal `ScheduleDefinition` values;
- the migrated result is exactly the canonical current writer output;
- migrating the already migrated payload is idempotent.

## Temporal behavior equivalence

Dataclass equality alone is not sufficient for a scheduling framework.

V1-02.D therefore also exercises observable occurrence behavior.

### v1 IntervalTrigger

The released v1 fixture is evaluated at references:

```text
before anchor
exactly at anchor
inside one interval
exactly at one occurrence
well after the anchor
```

The sequence returned by `next_after()` must remain identical after v1→v3 migration.

### v2 BusinessDayTrigger

The v2 fixture is bound to an exact business-calendar identity and revision.

Before and after migration, `next_after_with_calendar()` is evaluated across several months
with:

- ordinary Monday-Friday working days;
- an explicit holiday;
- an explicit extra working day;
- the exact `Europe/Paris` timezone from the persisted definition.

The occurrence trace must be identical.

### v3 AnyOfTrigger

The current v3 golden fixture combines Date, Interval and Cron children.

The compatibility suite verifies the same `next_after()` trace across multiple references
before and after canonical migration, including exhausted Date behavior and overlapping
temporal candidates.

## Trigger envelope guarantee

Trigger envelopes currently have one supported schema generation: v1.

V1-02.D therefore protects the meaning of v1 rather than pretending a nonexistent migration
history exists.

The migrated v1/v2 ScheduleDefinition fixtures must emit:

```json
{
  "kind": "...",
  "schema_version": 1,
  "config": { ... }
}
```

The v3 composite fixture additionally proves nested v1 envelopes for Date, Interval and Cron.

Unknown future Trigger versions remain fail-closed under V1-02.A.

## Generic SQL value semantics

The generic SQL value codec is still writer/floor v1.

V1-02.D qualifies semantic round trips for the durable value types currently encoded through
that envelope:

- `RetryPolicy`;
- `ConcurrencyPolicy`;
- `ExecutionPolicySnapshot`;
- `AttemptResult`;
- `ExecutionResult`;
- transitive `Failure` values.

The test does more than compare reconstructed objects.

### Retry behavior

A representative exponential retry policy is evaluated before and after round-trip for every
attempt number through its configured maximum.

The resulting `RetryDecision` sequence must remain identical.

The released v0.1.0a3 retry fixture is also evaluated against the released failure fixture.

### Concurrency behavior

A LIMIT/DROP policy is evaluated before and after round-trip for multiple active-instance
counts.

The resulting `ConcurrencyDecision` sequence must remain identical.

### Result semantics

Attempt and Execution terminal results preserve:

- terminal state;
- completion timestamp;
- failure category;
- failure code/message;
- retryable hint;
- ordered diagnostic details.

## Calendar semantics

BusinessCalendar value and collection codecs remain writer/floor v1.

The immutable pre-1.0 fixtures are decoded, rewritten and decoded again.

V1-02.D verifies:

- exact domain equality;
- calendar identity and revision preservation;
- deterministic collection ordering;
- unchanged `is_working_day()` decisions across a multi-day sample containing the committed
  holiday and extra-working-day exceptions;
- emitted schema version remains v1.

## Byte identity versus semantic identity

V1-02.B and V1-02.D intentionally protect different things.

```text
V1-02.B
unchanged writer generation
        ↓
same domain value
        ↓
same exact bytes required

V1-02.D
legacy writer generation
        ↓
decode + migrate
        ↓
different canonical bytes allowed
        ↓
same meaning and behavior required
```

For ScheduleDefinition v1/v2, rewriting into v3 necessarily changes bytes because the current
format adds the calendar field rules and versioned Trigger envelope structure.

That is a compatible migration only because semantic equivalence is executable.

## Executable evidence

The canonical V1-02.D compatibility suite is:

`tests/compatibility/test_v1_codec_semantic_equivalence.py`

It covers:

```text
ScheduleDefinition v1 → v3     domain + occurrence behavior
ScheduleDefinition v2 → v3     domain + calendar-aware occurrence behavior
ScheduleDefinition v3 → v3     idempotence + composite occurrence behavior
SQL value codec v1             domain + retry/concurrency behavior
BusinessCalendar v1            domain + working-day behavior
Calendar collection v1         domain + ordering/identity
current version matrix         exact executable writer versions
```

The immutable source fixtures remain owned by V1-02.B and are not rewritten by this lot.

## Evolution rule for 1.x

A future codec writer bump is incomplete until it supplies all of:

1. an explicit reader/migration path from every version at or above the frozen floor;
2. immutable golden bytes for the prior writer generation;
3. domain-equivalence assertions before/after migration;
4. behavioral-equivalence assertions where the value drives decisions;
5. fail-closed behavior for unknown future versions;
6. documentation of any intentionally changed semantics;
7. backup/rollback implications when persisted state is rewritten.

The frozen floor remains v1 throughout the 1.x line.

## V1-02 status

```text
V1-02.A  Persistence Version Floor & Policy          COMPLETE
V1-02.B  Immutable Golden Compatibility Fixtures     COMPLETE
V1-02.C  SQLite Forward Migration Qualification      COMPLETE
V1-02.D  Codec Migration & Semantic Equivalence      COMPLETE
V1-02.E  PostgreSQL Evolution / Rolling Upgrade      NEXT
V1-02.F  Backup / Rollback / Operations Contract     PLANNED
V1-02.G  Final Persistence Compatibility Review      PLANNED
```

## Deliberate boundary

V1-02.D does not:

- change any codec writer version;
- change SQLite or PostgreSQL schema versions;
- claim downgrade readability;
- claim mixed-version PostgreSQL workers are safe;
- introduce a cross-adapter migration tool;
- rewrite immutable V1-02.B fixtures;
- change package version, tag or publication state.

Those concerns remain with V1-02.E through V1-02.G where applicable.

---

**Status:** V1-02.D complete once the semantic-equivalence suite passes the full CI and
distribution qualification. Next: **V1-02.E — PostgreSQL Evolution / Rolling Upgrade**.
