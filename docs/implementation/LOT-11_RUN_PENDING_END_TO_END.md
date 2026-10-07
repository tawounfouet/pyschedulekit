# LOT-11 — run_pending() End-to-End Slice

## Goal

Deliver the first complete public scheduling slice:

```text
Clock
  ↓
Trigger
  ↓
Schedule
  ↓
Occurrence
  ↓
ExecutionRequest
  ↓
Execution
  ↓
Attempt
  ↓
LocalExecutor
  ↓
Python callable
  ↓
terminal result
```

The public entry point is:

```python
scheduler.run_pending()
```

## Public Scheduler facade

LOT-11 introduces the first deliberately small public `Scheduler`.

Current public methods:

- `register_target()`;
- `add_schedule()`;
- `run_pending()`.

This is not yet the final full API surface from the public API specification.

The first goal is a coherent, executable vertical slice.

## Default composition

```python
scheduler = Scheduler()
```

currently composes:

- SystemClock;
- InMemoryUnitOfWorkFactory;
- PythonTargetRegistry;
- LocalExecutor;
- SchedulerEngine;
- ExecutionService;
- ExecutionRunner;
- RunPendingService.

No background thread starts automatically.

## Testable composition

A deterministic Clock can be injected:

```python
clock = MutableClock(...)
scheduler = Scheduler(clock=clock)
```

The same Clock instance is used by:

- Scheduler creation reference;
- run_pending evaluation snapshot;
- Attempt start/completion timestamps;
- LocalExecutor Failure timestamps.

## Registering trusted targets

Persistent/declarative mode:

```python
target = scheduler.register_target(
    "refresh",
    refresh,
)

scheduler.add_schedule(
    target=target,
    trigger=...,
)
```

The returned TargetRef contains only the registry alias.

## Direct local callable convenience

For the in-memory local slice:

```python
scheduler.add_schedule(
    target=refresh,
    trigger=...,
)
```

is supported.

The Scheduler creates an internal registry alias based on ScheduleId.

This is process-local convenience.

It is not a portable persisted callable representation and does not weaken the rule against serializing Python executable objects.

## add_schedule()

Current shape:

```python
scheduler.add_schedule(
    target=...,
    trigger=...,
    id=None,
    timezone=None,
)
```

It returns:

```text
ScheduleId
```

A richer ScheduleHandle remains deferred.

## run_pending()

`run_pending()` executes exactly one bounded cycle.

It does not:

- sleep;
- poll continuously;
- spawn a thread;
- wait until all historical backlog is empty;
- apply implicit retry.

## Cycle phases

The cycle has three durable phases.

### Phase 1 — materialize due scheduling work

```text
evaluation_now = Clock.now()
      │
      ▼
SchedulerEngine.evaluate()
      │
      ▼
due Schedule
      │
      ▼
ExecutionRequest PENDING
+
Schedule checkpoint advanced
```

The evaluation clock snapshot is captured once for the SchedulerEngine cycle.

## Phase 2 — resume and dispatch PENDING requests

The cycle does not dispatch only requests materialized moments earlier.

It queries durable:

```text
ExecutionRequest.state == PENDING
```

and dispatches those requests.

This includes work left by an earlier process that may have crashed after materializing a request.

Therefore:

```text
durable PENDING request
+
new process
+
run_pending()
→ dispatch resumes
```

## Phase 3 — resume and execute QUEUED Executions

The cycle then queries durable:

```text
Execution.state == QUEUED
```

and invokes the ExecutionRunner.

This matters when target resolution previously failed.

Example:

```text
cycle 1
Execution QUEUED
target alias missing
→ TargetResolutionError

application registers alias

cycle 2
same QUEUED Execution
→ target resolves
→ Attempt RUNNING
→ SUCCESS
```

The work is not orphaned merely because its originating Schedule checkpoint has already advanced.

## Why durable queue resumption matters

Without PENDING and QUEUED recovery queries, a crash could create:

```text
ExecutionRequest durable
Schedule advanced
process dies before dispatch
```

and the next SchedulerEngine evaluation would not rediscover that same Schedule occurrence.

LOT-11 closes that gap at the in-memory vertical-slice level.

## Deterministic queue ordering

PENDING requests are ordered by:

```text
created_at ASC
RequestId ASC
```

QUEUED Executions are ordered by:

```text
created_at ASC
ExecutionId ASC
```

This provides deterministic one-shot processing.

## limit semantics

```python
scheduler.run_pending(limit=100)
```

currently applies the bound independently to:

1. due Schedule discovery;
2. PENDING request dispatch;
3. QUEUED Execution processing.

This makes every phase bounded.

It does not yet represent one global cross-phase work budget.

That can be refined with runtime/backpressure requirements later.

## Structured result

`run_pending()` returns:

```text
RunPendingResult
├── evaluation_now
├── materialized_request_ids
├── executions
├── schedule_conflicts
├── errors
├── succeeded
└── failed
```

`executions` contains workload attempts completed during this call.

`materialized_request_ids` contains only requests created/recovered from Schedule evaluation during this call.

Previously durable PENDING/QUEUED work may execute even when:

```text
materialized_request_ids == ()
```

## succeeded and failed

These counters refer to workload outcomes represented in `executions`.

A control-plane error such as unresolved target is not counted as a failed workload Attempt because no Attempt was started.

## Control-plane isolation

Per-request control-plane failures are reported through:

```text
RunPendingError
├── request_id
├── code
└── message
```

Current safe codes include:

- `executor.target_resolution`;
- `executor.error`;
- `persistence.conflict`.

The messages are intentionally generic and do not expose raw target exceptions or secret data.

## Workload failure versus run_pending error

Example target code:

```python
def task():
    raise RuntimeError("boom")
```

produces:

```text
Attempt FAILED
Execution FAILED
```

and appears in:

```text
RunPendingResult.executions
failed == 1
```

It does not become a `RunPendingError`.

By contrast, an unresolved registry alias produces:

```text
Execution stays QUEUED
no Attempt exists
RunPendingError(code="executor.target_resolution")
```

This preserves:

> control-plane error != workload Failure.

## Error isolation

A resolution error for one queued Execution does not prevent another queued Execution in the same cycle from succeeding.

This makes `run_pending()` useful as an operational batch boundary rather than an all-or-nothing façade over unrelated work.

## Backlog behavior

The SchedulerEngine still materializes at most one overdue occurrence per Schedule per cycle.

Therefore:

```text
10:00 due
10:10 due
10:20 due
evaluation_now = 10:35
```

one `run_pending()` materializes:

```text
10:00
```

The next call may materialize:

```text
10:10
```

This intentionally avoids embedding an implicit catch-up or skip policy.

## Recovery boundary

LOT-11 now recovers two durable pre-effect states:

```text
PENDING ExecutionRequest
QUEUED Execution
```

It does not yet recover:

```text
RUNNING Execution
RUNNING Attempt
```

Those require stale-running detection, leases/timeouts, idempotency-aware recovery, and a dedicated reconciliation lot.

## First end-to-end example

```python
from pyschedulekit import Duration, IntervalTrigger, Scheduler
from pyschedulekit.testing import MutableClock

clock = MutableClock(...)
scheduler = Scheduler(clock=clock)

calls = []

scheduler.add_schedule(
    id="refresh",
    target=lambda: calls.append("done"),
    trigger=IntervalTrigger(
        every=Duration.minutes(10),
        anchor=...,
    ),
)

clock.advance(Duration.minutes(10))

result = scheduler.run_pending()

assert calls == ["done"]
assert result.succeeded == 1
```

This is the first complete PyScheduleKit vertical slice.

## Root public exports

LOT-11 exposes the first qualified root imports:

- Scheduler;
- DateTrigger;
- IntervalTrigger;
- Duration;
- Instant;
- Timezone;
- TargetRef;
- ScheduleId;
- RunPendingResult;
- RunPendingError.

The root namespace remains intentionally small.

## Qualification scenarios

LOT-11 proves:

- direct callable does not run before due time;
- direct callable runs exactly once for a due occurrence;
- registered TargetRef executes successfully;
- evaluation_now is explicit in the cycle result;
- one overdue occurrence per Schedule per call;
- callable Exception becomes a failed workload Execution;
- unresolved target is isolated from another successful request;
- limit bounds deterministic Schedule discovery;
- no-due cycle is a no-op;
- unresolved queued Execution can run after later registry repair;
- durable PENDING request from a previous process is resumed and executed.

## Non-goals

LOT-11 does not implement:

- continuous runtime;
- sleep/wakeup;
- background threads;
- Cron;
- misfire;
- catch-up batching;
- coalescing;
- concurrency policy;
- automatic retry;
- timeout enforcement;
- durable SQL persistence;
- stale RUNNING recovery.

## Architecture milestone

Before LOT-11, individual components were qualified independently.

After LOT-11:

```text
public API
   ↓
Scheduler.run_pending()
   ↓
SchedulerEngine
   ↓
Persistence
   ↓
ExecutionService
   ↓
ExecutionRunner
   ↓
LocalExecutor
   ↓
real Python callable
```

works as one qualified slice.

## Exit criteria

LOT-11 is complete when:

- Scheduler is usable from the package root;
- run_pending is non-blocking and one-shot;
- a due IntervalTrigger reaches a successful real callable;
- PENDING requests survive process boundaries conceptually;
- QUEUED Executions can be resumed;
- control-plane failures are isolated and structured;
- workload Failure remains distinct;
- no hidden runtime loop is introduced;
- all CI gates are green.

## Next

After this milestone, the implementation can leave the narrow vertical slice and return to the deferred capability layers.

Recommended next:

`LOT-04 — CronTrigger`

Then the next capability wave can add:

```text
Misfire
Catch-Up
Concurrency
Retry
Runtime
Durable SQL persistence
Recovery
Distributed coordination
```
