# PyScheduleKit 1.0 Readiness

This area tracks the work required to turn the qualified pre-1.0 codebase into a durable
stable compatibility promise.

## Current verdict

```text
Runtime and domain qualification   GREEN
Public contract freeze             FROZEN
Persistence support policy         IN PROGRESS
Stable release activation          OPEN
Overall v1.0.0 decision             NO-GO
```

`NO-GO` does not mean that the scheduler is currently broken. It means that publishing
`1.0.0` today would promise compatibility before the exact promise, migration floor and
stable-release pipeline have been finalized.

The evidence and findings are recorded in the
[V1-00 readiness audit](./V1-00_READINESS_AUDIT.md).

## Delivery sequence

```text
V1-00  Readiness Audit                         COMPLETE
V1-01  Public Contract Freeze                  COMPLETE
V1-02  Persistence Compatibility Contract      IN PROGRESS
V1-03  Platform, Warning and Security Gates    PLANNED
V1-04  Consumer and Stable-Release Rehearsal   PLANNED
V1-05  Final GO/NO-GO and 1.0.0 Activation     PLANNED
```

## V1-01 breakdown

```text
V1-01.A  Public API Inventory & Classification       COMPLETE
V1-01.B  Root/API Stable Candidate Review            COMPLETE
V1-01.C  Secondary Namespace Policy                  COMPLETE
V1-01.D  Constructor / Method Signature Freeze       COMPLETE
V1-01.E  Protocol / Enum / Exception Freeze          COMPLETE
V1-01.F  Compatibility & Deprecation Policy          COMPLETE
V1-01.G  Executable Contract Snapshots               COMPLETE
V1-01.H  Final Public Contract Review                 COMPLETE
```

[V1-01.A](./V1-01A_PUBLIC_API_INVENTORY.md) records the exact current namespace inventory.
[V1-01.B](./V1-01B_ROOT_API_STABLE_CANDIDATE_REVIEW.md) reviews all 104 primary candidates
and partitions the intended 1.x surface into 63 root conveniences plus 41 advanced
`pyschedulekit.api`-only names. [V1-01.C](./V1-01C_SECONDARY_NAMESPACE_POLICY.md) then
freezes the secondary namespace policies: PostgreSQL stable-optional, testing stable-testing,
experimental outside SemVer, stable `__version__` presence, and legacy root redirects removed
before `1.0.0`. [V1-01.D](./V1-01D_SIGNATURE_FREEZE.md) adds an executable baseline for
39 consumer-authored constructors and 53 public methods, including parameter names, calling
modes and defaults. [V1-01.E](./V1-01E_PROTOCOL_ENUM_EXCEPTION_FREEZE.md) freezes
exported Protocol members, all public Enum names/values and the stable exception catch
categories. [V1-01.F](./V1-01F_COMPATIBILITY_DEPRECATION_POLICY.md) defines the canonical
1.x SemVer, typing and deprecation rules, including next-major-only removal for stable API.
[V1-01.G](./V1-01G_EXECUTABLE_CONTRACT_SNAPSHOTS.md) freezes the exact field and public
read-property structure of 21 stable operation-result types and their transitive records.
[V1-01.H](./V1-01H_FINAL_PUBLIC_CONTRACT_REVIEW.md) applies the final 63-name root, keeps
41 advanced names API-only, removes all 11 pre-1.0 root redirects and closes V1-01.

## V1-02 breakdown

```text
V1-02.A  Persistence Version Floor & Policy          COMPLETE
V1-02.B  Immutable Golden Compatibility Fixtures     COMPLETE
V1-02.C  SQLite Forward Migration Qualification      COMPLETE
V1-02.D  Codec Migration & Semantic Equivalence      COMPLETE
V1-02.E  PostgreSQL Evolution / Rolling Upgrade      COMPLETE
V1-02.F  Backup / Rollback / Operations Contract     NEXT
V1-02.G  Final Persistence Compatibility Review      PLANNED
```

[V1-02.A](./V1-02A_PERSISTENCE_VERSION_FLOOR_AND_POLICY.md) freezes the 1.x minimum
readable versions for SQLite, PostgreSQL, shared SQL values, ScheduleDefinition, Trigger
envelopes and calendar persistence. The floor is v1 for every currently versioned surface;
current writers remain SQLite v8, ScheduleDefinition v3 and v1 for the other listed formats.
[V1-02.B](./V1-02B_IMMUTABLE_GOLDEN_COMPATIBILITY_FIXTURES.md) commits seven append-only,
SHA-256-protected serialization fixtures from the public `v0.1.0a3` format and immutable
pre-1.0 commit `945ec173…`, and proves both legacy readability and exact byte reproduction
for unchanged writers.
[V1-02.C](./V1-02C_SQLITE_FORWARD_MIGRATION_QUALIFICATION.md) commits seven immutable
physical SQLite fixtures for schemas v1 through v7, protects both compressed and raw bytes,
and proves every supported entry point migrates through the production chain to v8 while
preserving integrity, foreign keys, the durable core graph, coordination rows, fencing
generations and retention completion timestamps.
[V1-02.D](./V1-02D_CODEC_MIGRATION_AND_SEMANTIC_EQUIVALENCE.md) proves
ScheduleDefinition v1/v2 migrate to canonical v3 without domain or occurrence-semantic drift,
and qualifies semantic round trips for Trigger envelopes, SQL values and business calendars.
[V1-02.E](./V1-02E_POSTGRES_EVOLUTION_AND_ROLLING_UPGRADE.md) freezes the
PostgreSQL 1.x rollout contract: same-contract schema-v1 overlap is live-qualified, arbitrary
N/N+1 overlap requires explicit release-pair evidence, schema-changing upgrades drain by
default, and any overlap-safe change must follow expand/migrate/contract with bidirectional
reader/writer compatibility.

## Operating rules

- do not bump the package to `1.0.0` before V1-05;
- do not create or push `v1.0.0` before an explicit final GO decision;
- do not publish another `0.x` or prerelease package;
- close compatibility questions before expanding the public feature surface;
- keep every supported guarantee mapped to executable evidence;
- treat unknown persisted versions as fail-closed unless an explicit migration exists.

## Feature boundary

Dependency/event triggers, schedule groups, dynamic updates, backfill and other new public
capabilities are not prerequisites by default. V1-01 may promote a capability to a 1.0
requirement only when the stable scope cannot be coherent without it. Otherwise it remains a
post-1.0 additive feature.

---

**Status:** V1-02.E PostgreSQL evolution / rolling-upgrade contract complete. V1-02.F Backup / Rollback / Operations Contract is next.
