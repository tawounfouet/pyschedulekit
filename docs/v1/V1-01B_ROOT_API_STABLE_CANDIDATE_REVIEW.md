# V1-01.B — Root/API Stable Candidate Review

**Baseline:** V1-01.A public namespace inventory  
**Primary candidates reviewed:** 104  
**Decision:** 63 root conveniences + 41 advanced API-only names  
**Runtime exports changed:** no

## Objective

V1-01.B reviews every current root/API candidate before signatures are frozen.

The key question is not whether a type is useful. It is whether consumers should be encouraged
to import it directly from the package root for the whole 1.x line.

The historical public-API specification says the root namespace must stay compact and that
advanced infrastructure concepts should remain optional. The current pre-1.0 root mirrors all
104 names from `pyschedulekit.api`, which is convenient but broader than that design goal.

## Decision

The 104 names remain **stable candidates in `pyschedulekit.api`**.

For the future 1.x root contract they are partitioned into:

```text
104 primary API candidates
├── 63 root conveniences
└── 41 advanced API-only names
```

No candidate is made internal by V1-01.B. The review narrows the intended root convenience
surface without removing the advanced API.

The current runtime root remains unchanged until the final V1-01 contract application. This
avoids mixing name-level review with the later signature/deprecation work.

## Root 1.x candidates — 63

These names express common scheduling intent, lifecycle control, durable snapshots, common
policies, common errors and built-in local adapters.

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

### Why these remain at root

The root should let a consumer express the normal mental model directly:

```text
Scheduler
  + TargetRef
  + Trigger
  + Time
  + Policies
  + Snapshots / Results
  + Common built-in adapters
```

`CancellationToken` remains at root because cooperative workload cancellation is directly
documented for application code.

`Trigger` remains at root because custom temporal rules are a first-class extension concept,
not merely infrastructure plumbing.

SQLite and local calendar providers remain root conveniences because they are dependency-free
built-ins and appear in ordinary single-process/durable usage.

## Advanced API-only candidates — 41

These names stay supported through `pyschedulekit.api`, but should not enlarge the default
root namespace.

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

## Rationale by advanced group

### Extension ports and composition-root types

`Clock`, `CalendarProvider`, `Executor`, `ExecutorRegistry`,
`UnitOfWorkFactory`, `ObservationSink`, `OutboxPublisher` and `PreparedTarget`
are valid public extension contracts. They remain stable candidates, but explicit
`pyschedulekit.api` imports make the advanced nature of that integration visible.

### Executor implementation plumbing

`LocalExecutor`, `AsyncioExecutor`, `RoutingExecutor`, target registries and
`HttpExecutor` are implementation/configuration tools. Normal Scheduler usage does not
require importing them.

### Diagnostic and decision detail

Admission, concurrency and retry decision records are valuable typed diagnostics, but they are
usually reached through higher-level results. Keeping them API-only avoids making the root a
complete mirror of every nested result type.

### Low-level identifiers and messaging

`AttemptId`, `RequestId`, `WorkerId`, outbox message types and detailed reconciliation
issues remain public for integrations and typing, while staying outside the common import path.

### Specialized errors

The root retains the normalized `PyScheduleKitError` hierarchy and common
not-found/runtime errors. More specialized recovery, reconciliation, target-resolution and
cancellation errors remain importable from `pyschedulekit.api`.

## Machine-readable decision

`src/pyschedulekit/api/_manifest.py` now contains:

- `ROOT_V1_PUBLIC_NAMES` — 63 names intended for the stable root;
- `API_ONLY_V1_PUBLIC_NAMES` — 41 advanced stable candidates;
- `STABLE_PUBLIC_NAMES` — unchanged 104-name complete primary API candidate set.

The two decision sets form an exact, sorted and disjoint partition of the 104 names.

## Executable evidence

`tests/architecture/test_v1_primary_api_decisions.py` proves:

- the 63 / 41 counts;
- sorted and disjoint sets;
- exact union with all 104 primary candidates;
- preservation of the core user-intent concepts at root;
- explicit API-only placement of representative extension contracts.

## Deliberate boundary

V1-01.B does **not** yet:

- alter `pyschedulekit.__all__`;
- remove existing pre-1.0 root imports;
- freeze any constructor or method signature;
- define deprecation timing for removing the 41 current root aliases;
- change the status of PostgreSQL, testing or experimental namespaces.

Those concerns belong to the following V1-01 lots.

---

**Status:** V1-01.B complete. Next: **V1-01.C — Secondary Namespace Policy**.
