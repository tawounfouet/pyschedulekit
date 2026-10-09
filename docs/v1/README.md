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
V1-01  Public Contract Freeze                  PLANNED
V1-02  Persistence Compatibility Contract      PLANNED
V1-03  Platform, Warning and Security Gates    PLANNED
V1-04  Consumer and Stable-Release Rehearsal   PLANNED
V1-05  Final GO/NO-GO and 1.0.0 Activation     PLANNED
```

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

**Status:** V1-00 complete. V1-01 Public Contract Freeze is the next implementation lot.
