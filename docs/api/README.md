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

`Scheduler` is the primary application-facing entry point.

### Registration and scheduling

- `Scheduler.register_target()` — register trusted local Python code and receive a
  declarative `TargetRef`.
- `Scheduler.register_http_target()` — register a trusted `HttpRequestSpec`.
- `Scheduler.register_executor()` — explicitly register one trusted `Executor` for a target kind.
- `Scheduler.add_schedule()` — persist a schedule using a `Trigger`, optional timezone,
  misfire, concurrency, retry and timeout policies.

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
| `CronDialect` | cron interpretation dialect |
| `CronAmbiguousTimePolicy` | DST-fold behavior |
| `CronNonexistentTimePolicy` | DST-gap behavior |

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
