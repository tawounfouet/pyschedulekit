# LOT-34 — Public API Hardening

## Goal

Turn the accumulated framework capabilities into an explicit library contract.

Before LOT-34, PyScheduleKit already had a broad root namespace, but that namespace mixed user-facing APIs with low-level distributed-coordination primitives and returned mutable domain aggregates from some public methods.

LOT-34 establishes the first compatibility boundary.

## Stable namespace

The canonical stable import surface is:

```python
import pyschedulekit.api as psk
```

The package root mirrors that stable surface for convenience.

```python
from pyschedulekit import Scheduler, IntervalTrigger, RetryPolicy
```

The stable symbol list is centralized in:

```text
pyschedulekit.api._manifest.STABLE_PUBLIC_NAMES
```

CI asserts that:

- the manifest is sorted and duplicate-free;
- `pyschedulekit.api.__all__` exactly matches it;
- root `pyschedulekit.__all__` matches it plus `__version__`;
- every root stable symbol is object-identical to the canonical API symbol.

## Experimental namespace

Distributed coordination internals are intentionally not part of the stable compatibility promise.

They live under:

```python
from pyschedulekit.experimental import (
    ExecutionClaim,
    ScheduleAdmissionLock,
)
```

Historical root imports remain temporarily resolvable through `__getattr__` and emit `PyScheduleKitDeprecationWarning`.

Experimental names are excluded from `__all__` and from the stable manifest.

## Public exception hierarchy

LOT-34 introduces:

```text
PyScheduleKitError
├── PyScheduleKitConfigurationError  (+ ValueError compatibility)
├── PyScheduleKitStateError          (+ RuntimeError compatibility)
├── PyScheduleKitNotFoundError       (+ LookupError compatibility)
└── PyScheduleKitTargetError         (+ RuntimeError compatibility)
```

Existing specific public exceptions inherit these categories while preserving compatibility with their former built-in exception families.

Examples:

```text
ScheduleNotFoundError
ExecutionNotFoundError
    → PyScheduleKitNotFoundError

RuntimeAlreadyRunningError
CrashRecoveryIncompleteError
ReconciliationIncompleteError
    → PyScheduleKitStateError

TargetResolutionError
UnsupportedTargetError
    → PyScheduleKitTargetError
```

## No mutable Aggregate Roots across Scheduler boundary

Public Scheduler methods must not return mutable domain aggregates.

LOT-34 changes the boundary:

```text
internal ExecutionRunResult
        │
        ▼
ExecutionRunSnapshot
        │
        └── ExecutionSnapshot (frozen)
```

`Scheduler.run_pending()` now returns the public immutable `RunPendingResult` from `pyschedulekit.api.results`.

`Scheduler.cancel_execution()` returns `ExecutionSnapshot` instead of `Execution`.

The snapshot preserves useful read ergonomics such as:

```python
result.executions[0].execution.id
result.executions[0].execution.state
result.executions[0].execution.policy_snapshot.timeout
```

without granting mutation authority over persistence-bound aggregates.

## Public result closure

Types appearing inside public results are now themselves exported as stable API:

```text
RequestId
AttemptId
ExecutionState
ExecutionPolicySnapshot
Failure
FailureCategory
RetryDecision
RetryDecisionReason
ConcurrencyDecision
ConcurrencyDecisionAction
AdmissionSnapshot
ExecutionRunSnapshot
```

This makes the public API typable end-to-end.

## Signature contract

CI snapshots the parameter names of established `Scheduler` methods, including constructor configuration and operational methods.

An accidental rename, parameter removal, or incompatible reordering therefore fails the build.

Intentional breaking changes must update the explicit API contract and version policy rather than landing silently.

## Versioning

LOT-34 advances the package to:

```text
0.1.0a1
```

`pyschedulekit._version.__version__` is the single source of truth.

`pyproject.toml` consumes that attribute dynamically, and CI verifies:

```text
importlib.metadata.version('pyschedulekit') == pyschedulekit.__version__
```

## Typing

PyScheduleKit now ships:

```text
src/pyschedulekit/py.typed
```

so type checkers can consume inline annotations under PEP 561.

## Compatibility policy

For the `0.x` line:

1. symbols in `STABLE_PUBLIC_NAMES` are the supported compatibility surface;
2. documented public method signatures should change deliberately and visibly;
3. experimental symbols may change without compatibility guarantees;
4. deprecated compatibility aliases emit `PyScheduleKitDeprecationWarning` before removal;
5. internal `domain`, `application`, `infrastructure`, and most `ports` module paths are implementation details unless re-exported by `pyschedulekit.api`.

Semantic Versioning becomes stricter as the project approaches 1.0, but LOT-34 establishes the mechanics now.

## Safety invariants

1. root and canonical stable API exports cannot drift silently;
2. experimental coordination primitives are excluded from the stable manifest;
3. legacy experimental root imports remain temporarily compatible and warn;
4. public Scheduler results do not expose mutable Execution aggregates;
5. nested public result types are importable from the stable namespace;
6. public operational exceptions share stable category bases;
7. previous built-in exception catch compatibility is preserved;
8. package/runtime versions cannot diverge silently;
9. inline typing is discoverable through PEP 561;
10. established Scheduler signatures are CI-qualified.

## Qualification

LOT-34 qualifies:

- stable export identity;
- legacy experimental compatibility warnings;
- exception-category inheritance;
- Scheduler parameter signatures;
- immutable run-pending execution snapshots;
- immutable cancellation result;
- stable nested public result types;
- package metadata/runtime version equality;
- PEP 561 package marker;
- Python 3.11, 3.12, and 3.13 compatibility.

## Roadmap status

```text
PRODUCTION MATURITY
────────────────────────────────────────────────────────
LOT-30  Observability                             ✅
LOT-31  Operational API                           ✅
LOT-32  Retention / Cleanup                       ✅
LOT-33  Additional Executors                      ✅
LOT-34  Public API Hardening                      ✅
```

The initial PyScheduleKit roadmap is complete.
