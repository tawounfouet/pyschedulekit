# LOT-08 — SchedulerEngine

## Goal

Introduce the first application service that turns a due Schedule checkpoint into a durable execution intent while advancing the Schedule atomically.

The central guarantee is:

```text
ExecutionRequest durable
AND
Schedule checkpoint advanced

or

neither
```

The engine must never advance `next_run_time` without preserving the corresponding intent to execute the occurrence.

## Why a minimal ExecutionRequest appears in LOT-08

The original roadmap places the full Execution lifecycle in LOT-09.

However, a SchedulerEngine that only:

```text
calculates Occurrence
→ advances Schedule
→ commits
```

would create a correctness hole:

```text
Schedule checkpoint committed
↓
process crashes
↓
no durable execution intent exists
↓
Occurrence silently lost
```

Therefore LOT-08 introduces only the smallest durable `ExecutionRequest` needed to preserve atomic scheduling semantics.

LOT-09 remains responsible for expanding the lifecycle and adding:

- Execution;
- Attempt;
- richer ExecutionRequest states;
- ExecutionResult / AttemptResult;
- Failure.

## Minimal ExecutionRequest

LOT-08 adds:

- `RequestId`;
- `ExecutionRequestState.PENDING`;
- immutable `ExecutionRequest`.

Current fields:

```text
RequestId
OccurrenceKey
TargetRef snapshot
created_at
state = PENDING
```

The object is intentionally small.

## Stable RequestId

Scheduler-created requests derive a deterministic identifier from:

```text
ScheduleId
+
ScheduleRevision
+
ScheduledAt
```

The derivation uses a canonical representation and SHA-256.

This supports reproducible identity for one scheduler-created Occurrence.

The uniqueness guarantee still remains primarily semantic:

```text
OccurrenceKey unique
```

A future manual rerun is not the same operation and may use a different request identity strategy.

## Target snapshot

The request copies the Schedule's current `TargetRef` at materialization time.

Therefore:

```text
Occurrence created under revision 1
→ request target = target from revision 1

Schedule later rescheduled
→ existing request remains unchanged
```

The request does not hold a live reference to mutable Schedule state.

## SchedulerEngine input

The engine does not read a Clock.

It receives:

```python
engine.evaluate(
    evaluation_now=...,
    limit=100,
)
```

One explicit `evaluation_now` is captured by the caller and reused for the whole evaluation cycle.

This preserves same-now semantics.

## Evaluation pipeline

```text
evaluation_now
      │
      ▼
discover due Schedule IDs
      │
      ▼
for each Schedule ID
      │
      ▼
new UnitOfWork
      │
      ▼
reload Schedule
      │
      ├─ no longer due → skip
      │
      ▼
OccurrencePlanner.current()
      │
      ▼
ExecutionRequest
      │
      ▼
advance next_run_time
      │
      ▼
save Schedule
      │
      ▼
single atomic commit
```

## Discovery versus authoritative re-check

The first query:

```python
list_due(now=evaluation_now, limit=...)
```

is discovery only.

Each selected Schedule is then reloaded inside its own UnitOfWork and checked again.

This prevents a stale discovery result from becoming authoritative.

Between discovery and evaluation, another actor may have:

- paused the Schedule;
- cancelled it;
- rescheduled it;
- advanced its checkpoint.

The per-Schedule transaction decides based on current durable state.

## Per-Schedule transaction

LOT-08 deliberately does not process an entire batch inside one transaction.

Instead:

```text
Schedule A → transaction A
Schedule B → transaction B
Schedule C → transaction C
```

Benefits:

- one conflict does not roll back successful unrelated Schedules;
- transaction scope remains small;
- optimistic concurrency has a narrow blast radius;
- later distributed claiming can evolve from the same structure.

## One occurrence per Schedule per cycle

LOT-08 materializes at most one due occurrence per Schedule in one evaluate() call.

Example:

```text
interval = 10 minutes
next_run_time = 10:00
evaluation_now = 10:35
```

First cycle:

```text
materialize 10:00
next_run_time → 10:10
```

Second cycle at the same evaluation_now:

```text
materialize 10:10
next_run_time → 10:20
```

The engine does not silently jump directly to 10:40.

Why?

Because doing so would embed a hidden misfire policy.

Misfire, catch-up and coalescing remain later explicit policy decisions.

## Advancing from scheduled_at

After materializing an Occurrence, the engine advances with:

```python
schedule.advance_next_run_after(
    reference=occurrence.scheduled_at,
)
```

not with:

```python
reference = evaluation_now
```

This preserves the Trigger's logical sequence without silently skipping missed candidates.

## Atomic cross-repository UnitOfWork

LOT-08 extends the in-memory UnitOfWork so one transaction owns:

```text
ScheduleRepository
+
ExecutionRequestRepository
```

Commit now performs:

```text
acquire store lock

validate all Schedule writes
validate all Request writes

if every validation succeeds:
    apply all Schedule writes
    apply all Request writes

release lock
```

No repository performs a private commit.

## Request uniqueness

The in-memory request repository enforces:

```text
RequestId unique
OccurrenceKey unique
```

This mirrors the future durable database constraints.

## Recovery-friendly idempotence

Before creating a request, the engine asks:

```python
get_by_occurrence(occurrence.key)
```

If a matching durable request already exists while the Schedule checkpoint still points to that Occurrence, the engine does not create a duplicate.

Instead it safely advances the Schedule checkpoint in the same transaction.

This provides a useful reconciliation behavior for future uncertain-commit or repair scenarios.

## Conflict behavior

Expected persistence conflicts are isolated per Schedule.

The evaluation result contains:

```text
requests
conflicts
```

A conflict on Schedule A does not prevent Schedule B from being evaluated.

The engine currently catches only `PersistenceConflictError`.

Unexpected programming/domain failures are not silently swallowed.

## SchedulerEvaluationResult

The immutable result contains:

```text
evaluation_now
requests
conflicts
```

This is an application result, not yet a final public API contract.

## Finite Trigger behavior

For a DateTrigger:

```text
Occurrence materialized
+
Trigger exhausted
↓
Schedule → COMPLETED
```

The ExecutionRequest and terminal Schedule transition are committed together.

## Failure atomicity proof

LOT-08 includes a deliberate request-identity collision test.

The scenario forces:

```text
request commit validation fails
```

and proves that:

```text
Schedule next_run_time remains unchanged
PersistenceVersion remains unchanged
correct Occurrence request does not appear
```

This demonstrates that request creation and checkpoint advancement are one transaction.

## Same-now proof

Multiple due Schedules evaluated in one cycle receive the same:

```text
created_at = evaluation_now
```

The engine does not call wall-clock time independently per item.

## Current guarantees

LOT-08 guarantees:

1. due discovery is deterministic;
2. every candidate is reloaded before authoritative evaluation;
3. one explicit evaluation_now is used per cycle;
4. one due Occurrence per Schedule is materialized per cycle;
5. Request creation and Schedule advancement are atomic;
6. existing request identity can repair an unadvanced checkpoint;
7. request TargetRef is snapshotted;
8. finite Trigger exhaustion completes the Schedule atomically;
9. expected persistence conflicts are isolated per Schedule;
10. no execution side effect occurs in SchedulerEngine.

## What SchedulerEngine does not do yet

LOT-08 does not:

- invoke TargetRef;
- create Execution;
- create Attempt;
- retry failures;
- evaluate MisfirePolicy;
- perform Catch-UpPolicy batching;
- apply ConcurrencyPolicy;
- sleep;
- own threads;
- publish network messages.

The engine decides and persists scheduling work.

It does not execute workload code.

## Architecture progression

```text
Clock snapshot
   │
   ▼
evaluation_now
   │
   ▼
SchedulerEngine
   │
   ├── ScheduleRepository
   ├── OccurrencePlanner
   └── ExecutionRequestRepository
          │
          ▼
  atomic UnitOfWork
          │
          ├── request durable
          └── checkpoint advanced

NEXT:
Execution lifecycle
```

## Qualification scenarios

LOT-08 tests prove:

- no due Schedule produces no request;
- due Schedule creates a request and advances checkpoint;
- all requests in one cycle share evaluation_now;
- overdue recurrence materializes one checkpoint per cycle;
- finite Trigger completes after materialization;
- TargetRef is snapshotted;
- pre-existing request repairs checkpoint without duplication;
- request commit conflict does not advance Schedule;
- one Schedule conflict does not block another;
- deterministic due limit is respected;
- invalid limit is rejected;
- RequestId is deterministic for one Occurrence;
- RequestId changes with ScheduleRevision;
- ExecutionRequest is immutable.

## Exit criteria

LOT-08 is complete when:

- SchedulerEngine has no hidden Clock access;
- durable intent and checkpoint advancement are atomic;
- same-now semantics are tested;
- overdue work is not silently skipped;
- per-Schedule conflicts are isolated;
- no Target is invoked;
- all quality gates are green.

## Next

`LOT-09 — ExecutionRequest & Execution Lifecycle`
