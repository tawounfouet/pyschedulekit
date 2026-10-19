# V1-02.B — Immutable Golden Compatibility Fixtures

**Scope:** committed byte-level compatibility fixtures for persisted serialization formats.

**Runtime behavior changed:** no  
**Persistence writer versions changed:** no  
**Package version changed:** no

## Objective

V1-02.A froze the minimum readable persisted version at v1 for every currently versioned
surface. V1-02.B now gives that promise immutable byte-level evidence.

Historically, many compatibility tests synthesized old payloads using the current encoder and
then edited version fields in memory. Those tests are useful, but they are not sufficient as
the long-term 1.x source of truth because the code generating the fixture can drift together
with the decoder.

V1-02.B therefore commits historical JSON bytes under:

`tests/fixtures/persistence/v1/`

and protects them with executable SHA-256 checks.

## Provenance classes

Two provenance classes are used.

### Released format

Source:

`v0.1.0a3`

This is the last public pre-1.0 PyPI/GitHub release.

At that tag:

- SQLite runtime schema was already v8;
- the shared SQL value codec was v1;
- ScheduleDefinition still used codec v1;
- Trigger payloads were flat and had no independent `schema_version`;
- calendar persistence did not yet exist;
- PostgreSQL persistence did not yet exist.

The released fixture vectors are derived from the deterministic serializer and the canonical
historical SQL-codec test vector at that immutable tag.

### Final pre-1.0 format checkpoint

Source commit:

`945ec1732fc03419f4d82bd81750bf7bf1032fd6`

This immutable commit is the V1-02.A baseline before golden-fixture work began.

At that checkpoint:

- ScheduleDefinition writer is v3;
- ScheduleDefinition v1/v2 remain readable;
- Trigger envelopes are v1;
- calendar value/collection codecs are v1;
- SQLite calendar-provider schema is v1;
- PostgreSQL runtime schema is v1.

Using an immutable commit rather than the moving `main` branch prevents provenance drift
during the rest of stabilization.

## Golden fixture inventory

### Released `v0.1.0a3`

```text
schedule_definition_v1_interval.json
retry_policy_v1_exponential.json
execution_result_v1_failure.json
```

These protect:

- ScheduleDefinition v1 flat-Trigger reads;
- generic SQL value codec v1;
- retry policy representation;
- execution result and normalized Failure representation.

### Pre-1.0 checkpoint

```text
schedule_definition_v2_business_day.json
schedule_definition_v3_composite.json
calendar_value_v1.json
calendar_collection_v1.json
```

These protect:

- legacy ScheduleDefinition v2 calendar binding;
- legacy flat BusinessDayTrigger representation;
- current ScheduleDefinition v3 writer;
- Trigger envelope schema v1;
- nested AnyOf child envelopes;
- BusinessCalendar value schema v1;
- BusinessCalendar collection schema v1.

## Immutability contract

The fixture set is append-only.

Every fixture is protected twice:

1. `tests/fixtures/persistence/v1/manifest.json` records its SHA-256;
2. `tests/compatibility/test_v1_golden_persistence_fixtures.py` contains the expected hash
   map independently.

The compatibility test fails if:

- a fixture byte changes;
- a fixture is removed;
- an undeclared JSON fixture appears;
- the manifest hash differs from the executable baseline.

This does not make repository history cryptographically immutable by itself; it makes every
intentional fixture mutation explicit in code review and CI rather than silently regenerable.

## Read compatibility evidence

The current decoder must successfully read all committed fixtures.

The test suite verifies semantic reconstruction of:

- the released interval ScheduleDefinition;
- its misfire/concurrency/retry/timeout configuration;
- released RetryPolicy v1;
- released failed ExecutionResult v1 with Failure details;
- pre-1.0 ScheduleDefinition v2 with BusinessDayTrigger and exact calendar revision;
- pre-1.0 ScheduleDefinition v3 with a three-child AnyOf Trigger;
- one BusinessCalendar value;
- one deterministic BusinessCalendar collection.

## Exact writer-byte evidence

For formats whose writer version remains unchanged, the current writer must reproduce the
golden bytes exactly.

V1-02.B currently enforces byte equality for:

- RetryPolicy / shared SQL value codec v1;
- ExecutionResult / Failure SQL value codec v1;
- ScheduleDefinition v3;
- BusinessCalendar value v1;
- BusinessCalendar collection v1.

ScheduleDefinition v1 and v2 are deliberately different: they are **read compatibility**
formats, not current write formats. The current writer upgrades them to v3 rather than
re-emitting legacy bytes.

## Why SQLite database files are not in this lot

V1-02.B protects serialization contracts only.

Historical SQLite database/schema fixtures require additional concerns:

- exact physical schema;
- metadata version;
- migration transactionality;
- preserved rows;
- forward migration through v1→v8;
- post-migration semantic checks.

Those belong to **V1-02.C — SQLite Forward Migration Qualification**.

Keeping them separate follows the project test specification: golden serialization files and
database migration tests protect different compatibility layers.

## PostgreSQL boundary

The public release `v0.1.0a3` predates PostgreSQL support, so there is no released
PostgreSQL fixture to capture.

PostgreSQL schema v1 begins in the final pre-1.0 line. Its migration/evolution evidence is
handled in V1-02.E because PostgreSQL currently has only one schema version and no historical
schema transition to fixture yet.

## Fixture change discipline

Future compatible persistence evolution must:

1. keep existing fixtures unchanged;
2. add a fixture for the new writer version;
3. add its immutable source provenance;
4. add its SHA-256 to manifest and executable baseline;
5. prove every frozen historical fixture remains readable;
6. prove semantic migration where a legacy format is upgraded.

A fixture correction is not a casual test maintenance task. If captured bytes are proven
incorrect for their declared source, the correction must be documented as a
compatibility-evidence incident.

## V1-02 status

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

V1-02.B does not:

- change runtime serialization;
- change any persistence version;
- claim current writers still emit v1/v2 ScheduleDefinition bytes;
- add SQLite database fixtures;
- introduce PostgreSQL schema migration;
- change package version, tag or publication state.

---

**Status:** V1-02.B golden fixtures are qualified and V1-02.C physical SQLite migration is
complete. Next: **V1-02.D — Codec Migration & Semantic Equivalence**.
