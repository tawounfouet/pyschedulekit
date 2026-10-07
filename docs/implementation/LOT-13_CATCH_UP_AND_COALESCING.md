# LOT-13 — Catch-Up & Coalescing

## Goal

Complete the two advanced misfire recovery modes introduced as domain concepts in LOT-12:

```text
CATCH_UP
COALESCE
```

Both must remain:

- deterministic;
- bounded;
- oldest-first where sequence matters;
- safe under durable recovery;
- explicit about checkpoint movement.

## Starting problem

Assume an IntervalTrigger scheduled:

```text
10:00
10:10
10:20
10:30
10:40
...
```

and the scheduler evaluates again at:

```text
10:35
```

The due backlog is:

```text
10:00
10:10
10:20
10:30
```

LOT-13 gives that backlog two different recovery meanings.

## Catch-Up

CATCH_UP preserves individual missed occurrences.

For the example:

```text
10:00 → ExecutionRequest
10:10 → ExecutionRequest
10:20 → ExecutionRequest
10:30 → ExecutionRequest
```

Each request retains its own OccurrenceKey.

Catch-Up never rewrites those four temporal facts into one synthetic occurrence.

## Coalescing

COALESCE intentionally discards new execution intent for older missed occurrences and keeps the latest due occurrence.

For the same example:

```text
10:00
10:10
10:20
10:30
   │
   ▼
COALESCE
   │
   ▼
10:30 → ExecutionRequest
```

The selected request still represents the real 10:30 occurrence.

It is not rewritten to 10:35.

## Bounded computation

Unbounded recovery is dangerous.

After a long outage, a high-frequency schedule may have millions of missed occurrences.

LOT-13 therefore adds:

```text
MisfirePolicy.max_occurrences
```

with a default of:

```text
100
```

and invariant:

```text
max_occurrences >= 1
```

Invalid limits fail immediately with:

```text
InvalidRecoveryLimitError
```

## Why one limit has different operational meaning

For CATCH_UP:

```text
max_occurrences = batch size
```

A larger backlog can safely progress across multiple cycles.

For COALESCE:

```text
max_occurrences = exact scan bound
```

Coalesce cannot safely select the true latest due occurrence if more due work exists beyond the scan bound.

Therefore the two actions intentionally react differently when the bound is reached.

## OccurrenceBacklog

OccurrencePlanner now exposes bounded reconstruction:

```text
OccurrenceBacklog
├── occurrences
└── has_more
```

The planner starts at the durable Schedule checkpoint and reconstructs due occurrences oldest-first.

Example:

```python
planner.due_backlog(
    schedule,
    until=evaluation_now,
    limit=3,
)
```

may return:

```text
occurrences:
10:00
10:10
10:20

has_more = true
```

The planner performs at most the requested batch plus one additional Trigger lookup to determine has_more.

It does not mutate the Schedule.

## Catch-Up batching

Given:

```text
due:
10:00
10:10
10:20
10:30

max_occurrences = 3
```

the first evaluation produces:

```text
requests:
10:00
10:10
10:20

next_run_time = 10:30
has_more = true
```

The next evaluation can then produce:

```text
request:
10:30

next_run_time = 10:40
has_more = false
```

This means large catch-up backlogs are drained incrementally rather than requiring one giant transaction.

## Oldest-first semantics

Catch-Up materialization order is explicitly:

```text
oldest due occurrence
        ↓
...
        ↓
newest occurrence in current batch
```

The in-memory repositories also prioritize pending and queued work by Occurrence scheduled_at when available.

This preserves chronological Catch-Up processing through the local vertical slice.

## Catch-Up transaction boundary

For one batch:

```text
reconstruct N due occurrences
        │
        ▼
create/reuse N ExecutionRequests
        +
advance Schedule checkpoint N times
        │
        ▼
single UnitOfWork commit
```

Therefore a committed batch does not leave the Schedule checkpoint advanced without its corresponding durable intents.

## Catch-Up and existing durable requests

Recovery remains idempotence-aware.

If the 10:00 request already exists:

```text
10:00 → reuse existing request
10:10 → create
10:20 → create
10:30 → create
```

The existing request is not duplicated.

OccurrenceKey uniqueness remains the durable identity barrier.

## Coalesce exactness

Coalesce needs the true latest due occurrence.

If the complete due backlog within the bound is:

```text
10:00
10:10
10:20
10:30
```

then:

```text
selected = 10:30
```

The checkpoint advances over all four considered occurrences to:

```text
10:40
```

while only the selected occurrence receives new durable intent.

## Coalesce fail-closed behavior

Suppose:

```text
due backlog:
10:00
10:10
10:20
10:30

max_occurrences = 3
```

The planner can prove:

```text
10:00
10:10
10:20
+ more due work exists
```

but it cannot prove the true latest due occurrence without exceeding the configured bound.

Therefore PyScheduleKit does not guess.

It returns:

```text
recovery_limit_schedules = (schedule_id,)
```

and performs:

```text
no new request
no checkpoint mutation
```

This is a deliberate fail-closed safety rule.

## Why Coalesce does not progress chunk by chunk

If Coalesce simply selected the latest occurrence of each bounded chunk, a backlog of 1000 occurrences with batch size 100 could generate ten executions.

That would violate the meaning of:

```text
coalesce all missed work into the latest due occurrence
```

Therefore chunked progress is correct for Catch-Up but incorrect for exact Coalesce.

## Existing durable intent during Coalesce

Coalescing cannot revoke an ExecutionRequest that was already committed.

Example:

```text
10:00 request already durable

new recovery evaluation sees:
10:00
10:10
10:20
10:30
```

Coalesce preserves:

```text
10:00 existing request
```

and may additionally create:

```text
10:30 latest request
```

It does not create new requests for 10:10 or 10:20.

This preserves the invariant:

> A recovery policy may decide whether to create new intent, but it does not erase intent already made durable.

## Grace still applies first

Catch-Up and Coalesce are recovery policies for true misfires.

If the current occurrence is still:

```text
ON_TIME
or
LATE_ELIGIBLE
```

MisfireEvaluator returns:

```text
MATERIALIZE
```

and SchedulerEngine processes only that occurrence normally.

It does not reconstruct a backlog merely because the configured policy is Catch-Up or Coalesce.

## RecoveryEvaluationRecord

SchedulerEngine now produces structured evidence:

```text
RecoveryEvaluationRecord
├── schedule_id
├── action
├── considered_occurrence_keys
├── materialized_occurrence_keys
└── has_more
```

This explains exactly what the recovery planner considered and what durable intents were retained or created.

It is diagnostic evidence, not authoritative state.

## SchedulerEvaluationResult

LOT-13 adds:

```text
recovery_records
recovery_limit_schedules
```

The older:

```text
unsupported_policy_schedules
```

field remains for API compatibility, but Catch-Up and Coalesce are no longer unsupported.

## RunPendingResult

The public one-shot cycle now exposes:

```text
recovery_limit_schedules
```

This lets an embedded application detect exact Coalesce recovery that could not be completed under the configured bound.

## Public API

Catch-Up:

```python
scheduler.add_schedule(
    target=task,
    trigger=trigger,
    misfire=MisfirePolicy.catch_up(
        max_occurrences=50,
    ),
)
```

Coalesce:

```python
scheduler.add_schedule(
    target=task,
    trigger=trigger,
    misfire=MisfirePolicy.coalesce(
        max_occurrences=500,
    ),
)
```

The bound should be chosen according to expected schedule frequency and maximum outage window.

## End-to-end Catch-Up

Given:

```text
interval = 10 minutes
first due = 10:10
evaluation = 10:45
max_occurrences = 2
```

the first run_pending() materializes and executes:

```text
10:10
10:20
```

The second run_pending() materializes and executes:

```text
10:30
10:40
```

The third call has no due work.

## End-to-end Coalesce

For the same backlog with a sufficiently large scan bound:

```text
10:10
10:20
10:30
10:40
   │
   ▼
one request for 10:40
   │
   ▼
one Execution
one Attempt
one callable invocation
```

## Durable ordering

InMemoryExecutionRequestRepository now orders PENDING work by:

```text
scheduled_at
created_at
RequestId
```

InMemoryExecutionRepository orders QUEUED work by the corresponding request scheduled_at when available.

This aligns recovery materialization and local execution order.

## Complexity bounds

For Catch-Up:

```text
O(max_occurrences)
per Schedule evaluation
```

and backlog may remain due for the next cycle.

For Coalesce:

```text
O(max_occurrences)
maximum scan
```

and overflow causes no mutation.

There is no unbounded historical replay in one evaluation.

## Safety properties

LOT-13 establishes:

1. Catch-Up batch size is finite.
2. Catch-Up progresses oldest-first.
3. Catch-Up can drain across repeated cycles.
4. Coalesce creates at most one new request for a complete bounded backlog.
5. Coalesce never guesses when the true latest occurrence is unknown.
6. Existing durable requests are preserved.
7. Schedule checkpoint advancement and new request creation share one transaction.
8. Occurrence identities are never rewritten to evaluation time.
9. Backlog reconstruction does not mutate the Schedule.
10. Grace classification happens before advanced recovery.

## Qualification scenarios

LOT-13 proves:

- bounded backlog reconstruction;
- has_more detection;
- invalid recovery limit rejection;
- Catch-Up oldest-first batch creation;
- Catch-Up continuation across cycles;
- Catch-Up reuse of existing requests;
- Coalesce latest-occurrence selection;
- Coalesce checkpoint advancement over discarded historical occurrences;
- Coalesce fail-closed behavior on bound overflow;
- Coalesce preservation of pre-existing durable intent;
- no backlog expansion while occurrence remains inside grace;
- public Catch-Up execution across multiple run_pending cycles;
- public Coalesce executes only one latest occurrence;
- public Coalesce overflow produces no workload execution.

## Non-goals

LOT-13 does not implement:

- execution concurrency admission;
- queue overflow policy;
- retry;
- timeout;
- runtime sleep/wakeup;
- distributed claims;
- SQL persistence;
- stale-running recovery.

## Architecture progression

```text
Occurrence
    │
    ▼
Misfire classification
    │
    ├── SKIP
    ├── RUN_NOW
    ├── CATCH_UP
    │      ↓
    │   bounded oldest-first batch
    │
    └── COALESCE
           ↓
        exact latest due
        or fail closed
```

## Exit criteria

LOT-13 is complete when:

- Catch-Up is bounded and oldest-first;
- Catch-Up drains across cycles;
- Coalesce selects the true latest due occurrence;
- Coalesce refuses incomplete bounded scans;
- durable intent is preserved;
- checkpoint movement remains transactional;
- public run_pending supports both actions;
- all Python quality gates are green.

## Next

`LOT-14 — Concurrency Policy Foundations`
