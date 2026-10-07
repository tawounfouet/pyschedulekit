# LOT-14 — Concurrency Policy Foundations

## Goal

Introduce explicit execution-admission policy without confusing concurrency with:

- scheduling;
- misfire recovery;
- retry;
- execution failure;
- distributed locking.

The central separation is:

```text
ConcurrencyEvaluator
        │
        ▼
SHOULD this request be admitted?

ConcurrencyCoordinator
        │
        ▼
CAN this process reserve capacity now?
```

LOT-14 implements both layers for the in-memory/local runtime.

## Why concurrency belongs after durable intent

SchedulerEngine still materializes ExecutionRequests first.

That means:

```text
Occurrence
   ↓
ExecutionRequest durable
   ↓
Concurrency admission
   ↓
Execution
```

A concurrency limit therefore controls execution admission.

It does not erase the historical fact that an occurrence generated durable intent.

## Policy snapshot location

ConcurrencyPolicy is frozen into each ExecutionRequest when SchedulerEngine materializes it.

This is deliberate.

Suppose:

```text
10:00 request materialized with max_instances=1

Schedule is later rescheduled with ALLOW
```

The existing 10:00 request keeps:

```text
max_instances=1
```

Its admission semantics are not retroactively rewritten.

## ConcurrencyPolicy

LOT-14 introduces:

```text
ConcurrencyPolicy
├── mode
├── max_instances
└── overflow
```

Modes:

```text
ALLOW
LIMIT
```

Overflow actions for LIMIT:

```text
QUEUE
DROP
```

## ALLOW

```python
ConcurrencyPolicy.allow()
```

always returns:

```text
ADMIT
```

regardless of current active instance count.

This preserves all pre-LOT-14 behavior by default.

## LIMIT

Example:

```python
ConcurrencyPolicy.limit(
    max_instances=1,
)
```

means:

```text
active_instances < 1
→ ADMIT

active_instances >= 1
→ QUEUE
```

because QUEUE is the default overflow behavior.

## DROP overflow

Explicit drop:

```python
ConcurrencyPolicy.limit(
    max_instances=1,
    overflow=ConcurrencyOverflowPolicy.DROP,
)
```

produces:

```text
active_instances >= 1
→ DROP
```

The request moves to a durable terminal state:

```text
ExecutionRequestState.DROPPED
```

No Execution is created.

## Invalid policy

A LIMIT policy requires:

```text
max_instances >= 1
```

Zero or negative values raise:

```text
InvalidConcurrencyPolicyError
```

ALLOW must not define max_instances.

## Pure evaluator

ConcurrencyEvaluator receives only:

```text
ConcurrencyPolicy
active_instances
```

and returns:

```text
ConcurrencyDecision
├── action
├── active_instances
└── max_instances
```

Possible decision actions:

```text
ADMIT
QUEUE
DROP
```

The evaluator performs no I/O and owns no lock.

## What counts as an active instance

LOT-14 treats every admitted non-terminal Execution as consuming one slot.

Therefore these states count:

```text
QUEUED
RUNNING
RETRY_WAIT
```

Terminal states do not count:

```text
SUCCESS
FAILED
CANCELLED
TIMED_OUT
```

This is intentionally conservative.

A queued Execution has already reserved capacity before an Attempt begins.

A RETRY_WAIT Execution also retains capacity so a later retry cannot unexpectedly violate the configured limit.

Retry semantics themselves remain a later lot.

## Scope

Concurrency scope in LOT-14 is:

```text
ScheduleId
```

Two schedules using the same target do not share a limit.

Example:

```text
Schedule A max_instances=1
Schedule B max_instances=1
```

may each have one active Execution simultaneously.

Target-level, tenant-level, queue-level, or arbitrary concurrency groups are deferred.

## WAITING_ADMISSION

When the limit is reached with QUEUE overflow:

```text
ExecutionRequest PENDING
        │
        ▼
WAITING_ADMISSION
```

No Execution exists yet.

The request remains a durable admission candidate for a later run_pending() cycle.

## DROPPED

When the limit is reached with DROP overflow:

```text
ExecutionRequest PENDING
        │
        ▼
DROPPED
```

DROPPED is terminal.

It is distinct from:

```text
CANCELLED
```

because concurrency overflow is a scheduler policy decision, not an external cancellation request.

## Process-local ConcurrencyCoordinator

The coordinator performs one serialized admission section:

```text
load ExecutionRequest
        │
        ▼
count non-terminal Executions for ScheduleId
        │
        ▼
ConcurrencyEvaluator
        │
        ├── QUEUE
        │      ↓
        │   WAITING_ADMISSION
        │
        ├── DROP
        │      ↓
        │   DROPPED
        │
        └── ADMIT
               ↓
          DISPATCHED request
          +
          QUEUED Execution
               ↓
             commit
```

The process-wide lock surrounds the count-and-transition operation.

This prevents two ConcurrencyCoordinator instances in the same Python process from both observing the same free slot.

## Transaction boundary

For ADMIT:

```text
request.mark_dispatched()
+
Execution creation
+
single UnitOfWork commit
```

For QUEUE:

```text
request.wait_for_admission()
+
commit
```

For DROP:

```text
request.drop()
+
commit
```

No workload side effect occurs during admission.

## Why QUEUED Execution already consumes capacity

run_pending() dispatches admission candidates before it starts queued executions.

Without slot reservation at QUEUED state:

```text
request A → QUEUED
request B checks only RUNNING count
request B → QUEUED
```

would violate max_instances=1 before either Attempt starts.

Counting QUEUED as active closes that gap.

## Retry-wait reservation

RETRY_WAIT also counts as non-terminal capacity.

That means:

```text
Execution A RETRY_WAIT
max_instances=1
new request B
→ B cannot be admitted yet
```

This is conservative and keeps concurrency behavior stable when retry policy is added.

A future policy may introduce an explicit option to release capacity during retry wait, but LOT-14 does not guess that behavior.

## run_pending flow

LOT-14 changes the one-shot cycle from unconditional dispatch to admission:

```text
SchedulerEngine
    ↓
durable ExecutionRequests
    ↓
list_admission_candidates()
    ↓
ConcurrencyCoordinator
    ├── ADMIT
    ├── QUEUE
    └── DROP
    ↓
list QUEUED Executions
    ↓
ExecutionRunner
```

Admission candidates include both:

```text
PENDING
WAITING_ADMISSION
```

so queued requests are retried automatically on later cycles.

## RunPendingResult

The result now exposes:

```text
admissions
```

with one AdmissionResult per attempted candidate.

Convenience projections:

```text
queued_request_ids
dropped_request_ids
```

These states are not counted as workload failures.

A request that is QUEUED or DROPPED due to concurrency never started an Attempt.

## Catch-Up interaction

Concurrency is evaluated after misfire recovery materialization.

Example:

```text
CATCH_UP materializes:
10:10
10:20

max_instances=1
overflow=QUEUE
```

One run_pending() does:

```text
10:10 → ADMIT → Execution QUEUED
10:20 → QUEUE → WAITING_ADMISSION

Execution 10:10 runs and completes
```

Next run_pending():

```text
10:20 WAITING_ADMISSION
        │
        ▼
slot now free
        │
        ▼
ADMIT
        │
        ▼
run
```

Thus Catch-Up can create durable backlog faster than concurrency allows execution, without losing occurrence identity.

## Catch-Up with DROP

With:

```text
max_instances=1
overflow=DROP
```

the same two requests become:

```text
10:10 → ADMIT
10:20 → DROPPED
```

Only one workload runs.

The dropped request remains durable evidence that the occurrence existed but admission policy intentionally rejected execution.

## Schedule independence

A later Schedule pause, cancel, or reschedule does not rewrite the policy snapshot of an already materialized request.

This follows the same principle already established for TargetRef and occurrence identity:

> Durable intent owns the semantics captured when that intent was created.

## Existing ExecutionService.dispatch()

ExecutionService.dispatch() remains as a low-level lifecycle primitive and for earlier LOT qualification.

The default public runtime path is now:

```text
RunPendingService
→ ConcurrencyCoordinator
→ Execution
```

Application code that needs concurrency guarantees must use the coordinator path rather than bypass admission through direct low-level dispatch.

A later API-hardening lot can reduce or formalize that low-level surface.

## Process-local guarantee

LOT-14 provides atomic admission serialization within one Python process.

A module-wide admission lock is shared by all ConcurrencyCoordinator instances in that process.

This protects:

```text
Scheduler A
Scheduler B
same process
same persistent in-memory store
```

from local count-and-admit races.

## What LOT-14 does not guarantee

A Python process lock cannot coordinate:

```text
process A
process B
different hosts
multiple workers
distributed schedulers
```

Therefore LOT-14 does not claim distributed max-instance enforcement.

That requires a durable coordination mechanism such as:

- transactional row claims;
- uniqueness constraints;
- compare-and-swap state;
- leases/fencing when necessary.

That belongs to the distributed coordination layer.

## Safety properties

LOT-14 establishes:

1. concurrency policy is immutable data;
2. policy is snapshot into durable ExecutionRequest;
3. default ALLOW preserves prior behavior;
4. LIMIT rejects invalid capacity;
5. QUEUED Executions reserve a slot;
6. RUNNING Executions reserve a slot;
7. RETRY_WAIT Executions reserve a slot;
8. terminal Executions free capacity;
9. WAITING_ADMISSION creates no Execution;
10. DROPPED creates no Execution;
11. different ScheduleIds have independent limits;
12. admission is serialized across coordinators in one process;
13. admission state and Execution creation commit atomically;
14. concurrency rejection is not a workload Failure.

## Qualification scenarios

LOT-14 proves:

- ALLOW always admits;
- LIMIT admits below capacity;
- default overflow queues at capacity;
- DROP overflow drops at capacity;
- invalid max_instances is rejected;
- negative active counts are rejected;
- request can transition PENDING → WAITING_ADMISSION → DISPATCHED;
- request can transition PENDING/WAITING_ADMISSION → DROPPED;
- DROPPED cannot later dispatch;
- policy snapshot survives Schedule reschedule;
- QUEUED Execution consumes a slot;
- terminal Execution releases a slot;
- RETRY_WAIT retains a slot;
- DROP creates no Execution;
- scope is per ScheduleId;
- ALLOW supports multiple non-terminal Executions;
- two distinct coordinators in one process cannot over-admit;
- public run_pending queues Catch-Up overflow and executes it on a later cycle;
- public DROP discards Catch-Up overflow without creating workload failure.

## Non-goals

LOT-14 does not implement:

- retry policy;
- timeout policy;
- arbitrary concurrency groups;
- target-level global limits;
- tenant-level limits;
- priority queues;
- queue expiration;
- distributed locks;
- leases;
- fencing tokens;
- multi-process atomic admission.

## Architecture progression

```text
Occurrence
   ↓
ExecutionRequest
   ↓
ConcurrencyEvaluator
   ↓
SHOULD
   ↓
ConcurrencyCoordinator
   ↓
CAN
   ├── ADMIT → Execution
   ├── QUEUE → WAITING_ADMISSION
   └── DROP  → DROPPED
```

## Exit criteria

LOT-14 is complete when:

- concurrency policy is pure and immutable;
- admission policy is snapshotted durably;
- queue/drop behavior is explicit;
- non-terminal Execution counting is deterministic;
- capacity is reserved before workload start;
- queued requests resume on later cycles;
- local admission races are serialized;
- concurrency remains distinct from retry and failure;
- public run_pending supports LIMIT end-to-end;
- all Python quality gates are green.

## Next

`LOT-15 — Retry Policy Foundations`
