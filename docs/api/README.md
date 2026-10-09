# PyScheduleKit Public API Reference

This document describes the **stable public surface currently exported by
`pyschedulekit` and `pyschedulekit.api`**.

The executable source of truth is
[`src/pyschedulekit/api/_manifest.py`](../../src/pyschedulekit/api/_manifest.py).
Architecture tests verify that every stable manifest name remains represented here.

For runnable behavior examples, start with the
[cookbook](../cookbook/README.md).

## Import contract

Preferred imports:

```python
from pyschedulekit import Duration, IntervalTrigger, Scheduler
```

or:

```python
import pyschedulekit.api as psk

scheduler = psk.Scheduler()
```

The root package mirrors the stable `pyschedulekit.api` surface.

Pre-1.0 development may still evolve contracts, but exported stable names are already
protected by manifest and identity tests. The project will make its full compatibility
promise at `1.0.0`.

## Scheduler facade

`Scheduler` is the primary application-facing entry point. Its optional `calendar_provider=`
composition-root parameter resolves exact calendar revisions for calendar-bound schedules.

### Registration and scheduling

- `Scheduler.register_target()` — register trusted local Python code and receive a
  declarative `TargetRef`.
- `Scheduler.register_http_target()` — register a trusted `HttpRequestSpec`.
- `Scheduler.register_executor()` — explicitly register one trusted `Executor` for a target kind.
- `Scheduler.add_schedule()` — persist a schedule using a `Trigger`, optional timezone,
  exact `CalendarSnapshotRef`, misfire, concurrency, retry and timeout policies.

### Inspection and control

- `Scheduler.inspect_schedule()` → `ScheduleSnapshot`
- `Scheduler.inspect_execution()` → `ExecutionSnapshot`
- `Scheduler.pause_schedule()` → `ScheduleSnapshot`
- `Scheduler.resume_schedule()` → `ScheduleSnapshot`
- `Scheduler.cancel_schedule()` → `ScheduleSnapshot`
- `Scheduler.cancel_execution()` → `ExecutionSnapshot`

### Runtime and operations

- `Scheduler.run_pending()` → one non-blocking scheduling cycle and `RunPendingResult`
- `Scheduler.run_forever()` → continuous adaptive scheduling loop
- `Scheduler.stop()` → request runtime-loop interruption
- `Scheduler.shutdown()` → coordinated shutdown returning `ShutdownResult`
- `Scheduler.health()` → `SchedulerHealth`
- `Scheduler.readiness()` → `SchedulerReadiness`
- `Scheduler.recover()` → `CrashRecoveryResult`
- `Scheduler.reconcile()` → `ReconciliationResult`
- `Scheduler.dispatch_outbox()` → `OutboxDispatchResult`
- `Scheduler.cleanup()` → `CleanupResult`

## Calendar model

| Public name | Role |
|---|---|
| `CalendarRef` | stable logical identity of one business calendar |
| `CalendarRevision` | positive immutable revision of calendar rules |
| `CalendarSnapshotRef` | deterministic reference to one exact calendar revision |
| `BusinessCalendar` | immutable working-week / holiday / exception rules |
| `CalendarProvider` | port resolving latest or exact calendar revisions |
| `InMemoryCalendarProvider` | thread-safe process-local provider implementation |
| `FileCalendarProvider` | read-only validated JSON snapshot provider loaded once at construction |
| `SqliteCalendarProvider` | durable revision-aware provider backed by an isolated SQLite schema |

CAL-01 binds an optional exact `CalendarSnapshotRef` into `ScheduleDefinition` and exposes
it through `ScheduleSnapshot.calendar`. CAL-02 resolves that exact revision through the
configured `CalendarProvider` and filters Date/Interval/Cron candidates by the Schedule's
local calendar date before they become occurrences. Catch-up/coalesce uses the same filter,
and missing revisions fail closed.

## CAL-03 BusinessDayTrigger

`BusinessDayTrigger` is the first built-in calendar-aware Trigger.

```python
from pyschedulekit import BusinessDayTrigger

first = BusinessDayTrigger(ordinal=1, hour=8)
second = BusinessDayTrigger(ordinal=2, hour=9, minute=30)
last = BusinessDayTrigger(ordinal=-1, hour=18)
```

It requires `Scheduler.add_schedule(calendar=...)`. The Schedule timezone defines the local
civil hour and the exact bound calendar revision defines working dates.

The trigger is monthly:

- positive ordinals count working dates from month start;
- negative ordinals count from month end;
- holidays are excluded;
- explicit extra working days are included;
- DST ambiguity and gap handling remain explicit;
- search is bounded and deterministic.

The trigger does not fetch calendars or contain country-specific holiday data.

## CAL-04 persistence compatibility

Schedule definitions are now written as persistence codec v3. Trigger configuration has its
own declarative version envelope:

```json
{
  "kind": "cron",
  "schema_version": 1,
  "config": {
    "expression": "0 6 * * *"
  }
}
```

Existing persisted v1/v2 definitions remain readable. Legacy flat Trigger payloads normalize
to the same domain Trigger and are rewritten in the current format on the next normal SQL
write. Unsupported future Schedule-definition or Trigger versions fail closed.

This migration contract is internal persistence behavior; it does not add a public migration
method or change the `Scheduler.add_schedule()` API.

## CAL-05 provider adapters

`FileCalendarProvider(path)` loads one strict versioned JSON collection at construction.
The effective provider snapshot does not change if the file is edited later.

`SqliteCalendarProvider(database)` stores exact calendar revisions in dedicated
`pyschedulekit_calendar_schema` and `pyschedulekit_business_calendars` tables. It may use
the same SQLite file as `SqliteUnitOfWorkFactory`; the schemas remain independent.

Both providers implement the same `CalendarProvider.resolve(reference, revision=...)`
contract as `InMemoryCalendarProvider`. Static missing/malformed/unsupported definitions
fail as `PyScheduleKitConfigurationError`.

CAL-05 intentionally does not introduce remote HTTP/SaaS calendar resolution.

## Time and trigger model

| Public name | Role |
|---|---|
| `Instant` | timezone-aware absolute time, normalized by the domain |
| `Duration` | elapsed-time value object |
| `Timezone` | explicit IANA timezone abstraction |
| `Clock` | injected time source contract |
| `Trigger` | trigger protocol |
| `DateTrigger` | one-shot absolute occurrence |
| `IntervalTrigger` | anchored fixed-rate recurrence |
| `CronTrigger` | calendar recurrence with explicit timezone semantics |
| `BusinessDayTrigger` | Nth working day of each month at one Schedule-local civil time |
| `AnyOfTrigger` | duplicate-free temporal union of two or more child triggers |
| `CronDialect` | cron interpretation dialect |
| `CronAmbiguousTimePolicy` | DST-fold behavior |
| `CronNonexistentTimePolicy` | DST-gap behavior |

### AnyOfTrigger

`AnyOfTrigger` runs one Schedule whenever any child rule is due:

```python
from pyschedulekit import AnyOfTrigger, Duration, Instant, IntervalTrigger

trigger = AnyOfTrigger(
    IntervalTrigger(every=Duration.minutes(10), anchor=Instant.parse("2026-01-01T10:10:00Z")),
    IntervalTrigger(every=Duration.minutes(15), anchor=Instant.parse("2026-01-01T10:15:00Z")),
)
```

For each lookup it asks every child for its next candidate and returns the earliest one.
When several children produce the same `Instant`, the Schedule emits that occurrence once.

The public contract is deliberately bounded:

- at least two children are required;
- nested `AnyOfTrigger` values flatten into one union;
- at most 64 flattened children are accepted;
- children must implement the ordinary pure temporal `Trigger` protocol;
- calendar-aware children, including `BusinessDayTrigger`, are rejected;
- `AllOfTrigger` / intersection semantics are not part of the public API.

Composite definitions and checkpoints round-trip across InMemory, SQLite and PostgreSQL.
SQLite/PostgreSQL payloads use the versioned Trigger codec and normalize valid nested rows
on the next normal write.

## Schedule model

| Public name | Role |
|---|---|
| `ScheduleId` | schedule identity |
| `ScheduleState` | lifecycle state |
| `ScheduleSnapshot` | immutable operational schedule view |
| `TargetRef` | declarative executable-target reference |
| `GracePeriod` | lateness grace value used by scheduling policies |

## Misfire, concurrency and retry policies

### Misfire

- `MisfirePolicy`
- `MisfirePolicyAction`

### Concurrency

- `ConcurrencyPolicy`
- `ConcurrencyMode`
- `ConcurrencyOverflowPolicy`
- `ConcurrencyDecision`
- `ConcurrencyDecisionAction`
- `AdmissionSnapshot`

### Retry and backoff

- `RetryPolicy`
- `RetryDecision`
- `RetryDecisionReason`
- `FixedBackoff`
- `ExponentialBackoff`
- `NoBackoff`

## Execution model

| Public name | Role |
|---|---|
| `ExecutionId` | logical execution identity |
| `RequestId` | durable execution-request identity |
| `AttemptId` | individual attempt identity |
| `ExecutionState` | execution lifecycle state |
| `ExecutionSnapshot` | immutable operational execution view |
| `ExecutionRunSnapshot` | result snapshot returned from a run cycle |
| `ExecutionPolicySnapshot` | policy values captured for an execution |
| `Failure` | structured execution failure |
| `FailureCategory` | failure classification |
| `CancellationToken` | cooperative cancellation contract |

## Cycle results

`RunPendingResult` reports the outcome of one `Scheduler.run_pending()` cycle.

`RunPendingError` represents isolated cycle errors that do not necessarily terminate the
scheduler runtime.

## Persistence

| Public name | Role |
|---|---|
| `UnitOfWorkFactory` | persistence boundary used by `Scheduler` |
| `SqliteUnitOfWorkFactory` | durable SQLite implementation |

PostgreSQL is a stable **optional namespace** rather than a root export:

```python
from pyschedulekit.postgres import (
    PostgresUnitOfWorkFactory,
    TransientPersistenceError,
)
```

Install it with `pip install "pyschedulekit[postgres]"`.

The root package deliberately does not import PostgreSQL support so the base install keeps
zero runtime dependencies. SQLite and PostgreSQL satisfy the same shared adapter contract.

## Optional PostgreSQL namespace

`pyschedulekit.postgres` exports:

- `PostgresUnitOfWorkFactory` — durable PostgreSQL UnitOfWork factory.
- `TransientPersistenceError` — retryable whole-transaction abort signal for deadlock or
  serialization failure.

Production assumptions, supported PostgreSQL majors and migration policy are documented in
[PostgreSQL support and migration](../postgres/SUPPORT_AND_MIGRATION.md).

## Executors and targets

### Core executor contracts

- `Executor`
- `PreparedTarget`
- `ExecutorOutcome`
- `ExecutorRegistry` — instance-owned explicit registry mapping `TargetRef.kind` to an
  `Executor`; no process-global or import-time plugin mutation.
- `RoutingExecutor`

### Local Python

- `LocalExecutor`
- `PythonTargetRegistry`

### Async Python

- `AsyncioExecutor` — execute explicitly registered trusted `async def` targets behind
  the synchronous Executor boundary.
- `AsyncPythonTargetRegistry` — process-local registry for trusted async callables.
- `Scheduler.register_async_target()` — register one async callable and receive a
  `TargetRef(kind="python_async", ...)`.
- `TargetRef.async_python()` — declarative async Python target reference.

Passing an `async def` directly to `Scheduler.add_schedule()` is also supported; the
Scheduler detects coroutine functions and registers them in the async registry.

The Scheduler itself remains synchronous. Async workload execution does not introduce async
persistence methods or an `AsyncScheduler`.

### HTTP

- `HttpExecutor`
- `HttpTargetRegistry`
- `HttpRequestSpec`
- `HttpMethod`

Executor plugins are registered explicitly:

```python
scheduler.executor_registry.register("workflow", workflow_executor)
```

The registry is owned by one Scheduler/composition root, so separate Scheduler instances
may use different plugins in the same process. Registration is thread-safe and dynamic:
`RoutingExecutor` resolves the current registry at prepare time.

PyScheduleKit does **not** auto-import executors from persisted strings or mutate a hidden
global registry. Automatic package-entry-point discovery is intentionally deferred.

Target registries contain **trusted process-local executable configuration**. Durable
schedule state stores declarative references; executable Python objects are not serialized
into persistence.

## Observability

- `Observation`
- `ObservationSink`
- `InMemoryObservationSink`

The observation API is intended for scheduler lifecycle and execution diagnostics rather
than hidden logging side effects.

## Outbox

- `OutboxMessageId`
- `OutboxMessage`
- `OutboxState`
- `OutboxPublisher`
- `OutboxDispatchResult`
- `OutboxPublishError`

The outbox boundary separates durable intent from external publication.

## Recovery and reconciliation

### Crash recovery

- `CrashRecoveryResult`
- `CrashRecoveryError`
- `CrashRecoveryActiveRuntimeError`
- `CrashRecoveryIncompleteError`

### Reconciliation

- `ReconciliationResult`
- `ReconciliationIssue`
- `ReconciliationActiveRuntimeError`
- `ReconciliationIncompleteError`

## Retention and cleanup

- `RetentionPolicy` — explicit bounded cleanup policy for execution history and published
  outbox state.
- `CleanupResult` — reports what bounded cleanup removed.

## Runtime, shutdown and worker identity

- `WorkerId`
- `SchedulerHealth`
- `SchedulerReadiness`
- `ShutdownMode`
- `ShutdownResult`
- `RuntimeAlreadyRunningError`

## Error model

All framework errors derive from `PyScheduleKitError` or a more specific public family.

### General families

- `PyScheduleKitError`
- `PyScheduleKitConfigurationError`
- `PyScheduleKitStateError`
- `PyScheduleKitNotFoundError`
- `PyScheduleKitTargetError`

### Operational / target errors

- `ScheduleNotFoundError`
- `ExecutionNotFoundError`
- `ExecutionCancelledError`
- `TargetResolutionError`
- `UnsupportedTargetError`

### Compatibility warning

- `PyScheduleKitDeprecationWarning`

## Legacy root compatibility names

The following names exist only as legacy root-level compatibility redirects and are **not
part of the stable public manifest**:

- `AdmissionLockOwnershipError`
- `AdmissionToken`
- `ClaimOwnershipError`
- `ClaimToken`
- `ExecutionClaim`
- `ExecutionClaimHandle`
- `ExecutionClaimState`
- `LatenessStatus`
- `ScheduleAdmissionLock`
- `ScheduleAdmissionLockHandle`
- `ScheduleAdmissionLockState`

New code should not depend on these legacy root names.

## Testing helpers

Deterministic testing helpers such as `MutableClock` and `FixedClock` are available from
`pyschedulekit.testing` and are used heavily in the cookbook and project test suite.

They are intentionally documented separately from the stable root/API manifest.

## Public-surface change rule

Changing the stable surface requires coordinated changes to:

1. `src/pyschedulekit/api/_manifest.py`;
2. `src/pyschedulekit/api/__init__.py`;
3. `src/pyschedulekit/__init__.py`;
4. public API contract tests;
5. this API reference;
6. cookbook/examples when behavior changes.

The documentation test added by POST-03 makes item 5 executable.
