# V1-01.H — Final Public Contract Review

**Scope:** apply and verify the complete Python public contract produced by V1-01.A through
V1-01.G.

**Runtime scheduling behavior changed:** no  
**Public import surface changed:** yes, final pre-1.0 contract application  
**Package version changed:** no

## Objective

V1-01.H is the final integration review for the public Python surface before persistence
compatibility work begins.

The earlier V1-01 lots deliberately separated inventory, placement, signatures, structural
contracts and compatibility policy. This lot applies those decisions to the actual runtime
namespaces and verifies that they form one coherent contract.

## Final primary namespace contract

The stable primary contract is:

```text
pyschedulekit.api
└── 104 stable names
    ├── 63 common names also exported from pyschedulekit
    └── 41 advanced names available only from pyschedulekit.api

pyschedulekit
├── 63 stable convenience names
└── __version__
```

The two 63/41 sets are sorted, disjoint and form an exact partition of
`STABLE_PUBLIC_NAMES`.

The package root is intentionally not a mirror of the complete API.

## Root convenience surface

The 63-name root is the surface for normal application code:

```text
AnyOfTrigger
BusinessCalendar
BusinessDayTrigger
CalendarRef
CalendarRevision
CalendarSnapshotRef
CancellationToken
CleanupResult
ConcurrencyMode
ConcurrencyOverflowPolicy
ConcurrencyPolicy
CrashRecoveryResult
CronAmbiguousTimePolicy
CronDialect
CronNonexistentTimePolicy
CronTrigger
DateTrigger
Duration
ExecutionId
ExecutionNotFoundError
ExecutionSnapshot
ExecutionState
ExponentialBackoff
Failure
FailureCategory
FileCalendarProvider
FixedBackoff
GracePeriod
HttpMethod
HttpRequestSpec
InMemoryCalendarProvider
Instant
IntervalTrigger
MisfirePolicy
MisfirePolicyAction
NoBackoff
OutboxDispatchResult
PyScheduleKitConfigurationError
PyScheduleKitDeprecationWarning
PyScheduleKitError
PyScheduleKitNotFoundError
PyScheduleKitStateError
PyScheduleKitTargetError
ReconciliationResult
RetentionPolicy
RetryPolicy
RunPendingError
RunPendingResult
RuntimeAlreadyRunningError
ScheduleId
ScheduleNotFoundError
ScheduleSnapshot
ScheduleState
Scheduler
SchedulerHealth
SchedulerReadiness
ShutdownMode
ShutdownResult
SqliteCalendarProvider
SqliteUnitOfWorkFactory
TargetRef
Timezone
Trigger
```

`pyschedulekit.__all__` contains exactly those names plus `__version__`.

## Advanced stable API-only surface

The following 41 names remain fully stable but are intentionally explicit advanced imports:

```text
AdmissionSnapshot
AsyncPythonTargetRegistry
AsyncioExecutor
AttemptId
CalendarProvider
Clock
ConcurrencyDecision
ConcurrencyDecisionAction
CrashRecoveryActiveRuntimeError
CrashRecoveryError
CrashRecoveryIncompleteError
ExecutionCancelledError
ExecutionPolicySnapshot
ExecutionRunSnapshot
Executor
ExecutorOutcome
ExecutorRegistry
HttpExecutor
HttpTargetRegistry
InMemoryObservationSink
LocalExecutor
Observation
ObservationSink
OutboxMessage
OutboxMessageId
OutboxPublishError
OutboxPublisher
OutboxState
PreparedTarget
PythonTargetRegistry
ReconciliationActiveRuntimeError
ReconciliationIncompleteError
ReconciliationIssue
RequestId
RetryDecision
RetryDecisionReason
RoutingExecutor
TargetResolutionError
UnitOfWorkFactory
UnsupportedTargetError
WorkerId
```

Consumers import those through:

```python
import pyschedulekit.api as psk
```

or explicit `from pyschedulekit.api import ...` statements.

Removing them from the root does not make them internal. Their V1 signatures, Protocol/Enum
contracts, result structures and compatibility guarantees remain protected through the
complete stable API namespace.

## Legacy root redirect removal

The 11 pre-1.0 compatibility redirects are now physically removed from
`pyschedulekit`:

```text
AdmissionLockOwnershipError
AdmissionToken
ClaimOwnershipError
ClaimToken
ExecutionClaim
ExecutionClaimHandle
ExecutionClaimState
LatenessStatus
ScheduleAdmissionLock
ScheduleAdmissionLockHandle
ScheduleAdmissionLockState
```

There is no root `__getattr__` compatibility shim.

Those names remain available only from `pyschedulekit.experimental`, where they are
explicitly outside the 1.x SemVer promise.

This fulfills the V1-01.C policy decision before the stable 1.0 contract is activated.

## Final namespace classifications

`PUBLIC_NAMESPACE_CLASSIFICATIONS` now records:

```text
pyschedulekit               stable
pyschedulekit.api           stable
pyschedulekit.postgres      stable-optional
pyschedulekit.testing       stable-testing
pyschedulekit.experimental  experimental
```

The machine-readable final state also records:

```text
V1_PUBLIC_CONTRACT_STATUS = "frozen"
LEGACY_ROOT_REDIRECT_V1_POLICY = "removed-before-v1.0.0"
```

## Evidence inherited from V1-01

The final contract is not only a name list.

```text
V1-01.A  exact namespace inventory
V1-01.B  63 root / 41 API-only partition
V1-01.C  secondary namespace policies
V1-01.D  constructor and method signatures
V1-01.E  Protocol / Enum / exception contracts
V1-01.F  SemVer / typing / deprecation policy
V1-01.G  result field and property snapshots
V1-01.H  runtime application + final integration review
```

Together these define the Python-facing compatibility promise intended for the 1.x line.

## Executable evidence

`tests/architecture/test_v1_final_public_contract.py` verifies:

- final `V1_PUBLIC_CONTRACT_STATUS`;
- exact 63/41/104 counts and partition;
- exact root `__all__`;
- identity between every root convenience and its canonical API object;
- presence of all 41 advanced names in `pyschedulekit.api`;
- absence of all 41 advanced names from the root;
- physical absence of the legacy root `__getattr__` shim;
- continued availability of the 11 names in `pyschedulekit.experimental`;
- exact PostgreSQL, testing and experimental secondary surfaces;
- final namespace classifications.

Existing A-G architecture tests continue to protect the deeper contract dimensions.

## Consumer migration inside the repository

Current documentation and executable consumers are updated to match the final partition.

Normal scheduling examples continue to import common names from `pyschedulekit`.
Advanced examples use `pyschedulekit.api`, including executor composition, async adapters,
observability and detailed outbox contracts.

This migration is performed before 1.0.0 specifically so the first stable release starts with
the intended namespace shape rather than carrying pre-1.0 aliases indefinitely.

## Deliberate boundary

V1-01.H does not:

- change scheduling/runtime semantics;
- change the package version;
- define persistence compatibility floors;
- add Python 3.14 to the declared support gate;
- change release workflow activation;
- create a tag, GitHub Release or PyPI publication.

Those remaining release blockers are handled by V1-02 through V1-05.

## V1-01 closure

After H passes the complete CI and distribution qualification:

```text
Public Contract Freeze = COMPLETE
```

The next workstream is:

**V1-02 — Persistence Compatibility Contract**

That lot will define the stable readable floor and migration guarantees for SQLite schemas,
schedule definitions, Trigger envelopes, calendar codecs and PostgreSQL persistence.

---

**Status:** final V1-01 public contract applied. V1-02 is next.
