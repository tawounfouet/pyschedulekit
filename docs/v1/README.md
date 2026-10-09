# PyScheduleKit 1.0 Readiness

This area tracks the work required to turn the qualified pre-1.0 codebase into a durable
stable compatibility promise.

## Current verdict

```text
Runtime and domain qualification   GREEN
Public contract freeze             OPEN
Persistence support policy         OPEN
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
V1-01  Public Contract Freeze                  IN PROGRESS
V1-02  Persistence Compatibility Contract      PLANNED
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
V1-01.F  Compatibility & Deprecation Policy          NEXT
V1-01.G  Executable Contract Snapshots               PLANNED
V1-01.H  Final Public Contract Review                 PLANNED
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
categories.

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

**Status:** V1-01.E structural contract baseline recorded. V1-01.F Compatibility & Deprecation Policy is next.
