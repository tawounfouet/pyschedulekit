# LOT-12 — Misfire Policy Foundations

## Goal

Introduce explicit lateness classification and recovery policy semantics without mixing misfire with retry, concurrency, or runtime wake-up behavior.

The core question is:

> An occurrence was scheduled for a past instant. Is it still acceptable to materialize it, or has it become a true misfire?

LOT-12 separates that question into two steps:

```text
scheduled_at + evaluation_now + grace
                │
                ▼
       lateness classification
                │
                ▼
          policy decision
```

## Misfire is not failure

A misfire happens before workload execution.

Therefore:

```text
MISFIRE
≠
Attempt failure
≠
Retry decision
```

A target can succeed or fail only after an Attempt actually starts.

A skipped misfire creates no Attempt at all.

## Temporal classification

LOT-12 introduces three temporal states:

```text
ON_TIME
LATE_ELIGIBLE
MISFIRED
```

Given:

```text
scheduled_at
grace
deadline = scheduled_at + grace
evaluation_now
```

the classification rules are:

### ON_TIME

```text
evaluation_now == scheduled_at
```

### LATE_ELIGIBLE

```text
scheduled_at < evaluation_now <= deadline
```

### MISFIRED

```text
evaluation_now > deadline
```

The deadline boundary is inclusive.

An occurrence evaluated exactly at its grace deadline is still eligible.

## Not-due input

The lateness classifier only accepts due occurrences.

If:

```text
evaluation_now < scheduled_at
```

it raises:

```text
OccurrenceNotDueError
```

This prevents an early state from being silently folded into the lateness model.

## GracePeriod

The existing `GracePeriod` Value Object becomes operational in LOT-12.

Example:

```python
GracePeriod.seconds(60)
```

For an occurrence scheduled at 10:00:00:

```text
10:00:00 → ON_TIME
10:00:30 → LATE_ELIGIBLE
10:01:00 → LATE_ELIGIBLE
10:01:01 → MISFIRED
```

## MisfirePolicy

A ScheduleDefinition now owns an immutable:

```text
MisfirePolicy
├── action
└── grace
```

The configured actions are:

```text
SKIP
RUN_NOW
CATCH_UP
COALESCE
```

## Default compatibility policy

The default is:

```python
MisfirePolicy.run_now(
    grace=GracePeriod.zero(),
)
```

This intentionally preserves the behavior implemented before LOT-12.

Previously, any due occurrence was materialized when the SchedulerEngine saw it.

With zero grace plus RUN_NOW:

```text
exactly due
→ ON_TIME
→ materialize

late by any positive amount
→ MISFIRED
→ RUN_NOW
→ materialize
```

No existing schedule changes behavior merely because the explicit misfire model now exists.

## Classification and decision are distinct

LOT-12 introduces:

```text
LatenessClassifier
```

and:

```text
MisfireEvaluator
```

The classifier knows nothing about recovery policy.

The evaluator combines:

```text
classification + MisfirePolicy
```

to produce a:

```text
MisfireDecision
```

This prevents temporal facts and business policy from collapsing into one object.

## Decision actions

A policy configuration is not exactly the same thing as an engine action.

LOT-12 distinguishes:

```text
MisfirePolicyAction
├── SKIP
├── RUN_NOW
├── CATCH_UP
└── COALESCE
```

from:

```text
MisfireDecisionAction
├── MATERIALIZE
├── SKIP
├── CATCH_UP
└── COALESCE
```

Why?

Because an occurrence that is ON_TIME or LATE_ELIGIBLE must be materialized even if the configured recovery policy is SKIP.

The recovery policy is consulted only for a true MISFIRED classification.

## SKIP

For a true misfire:

```python
MisfirePolicy.skip(...)
```

produces:

```text
MisfireDecisionAction.SKIP
```

SchedulerEngine then:

```text
does not create ExecutionRequest
advances Schedule.next_run_time
commits the Schedule mutation
```

For a finite DateTrigger, skipping the only occurrence exhausts the Trigger and moves the Schedule to:

```text
COMPLETED
```

## RUN_NOW

For a true misfire:

```python
MisfirePolicy.run_now(...)
```

produces:

```text
MisfireDecisionAction.MATERIALIZE
```

The original occurrence identity is preserved.

Example:

```text
scheduled_at = 10:00
evaluation_now = 10:35
```

The request still contains:

```text
OccurrenceKey.scheduled_at = 10:00
```

while:

```text
ExecutionRequest.created_at = 10:35
```

This is critical.

RUN_NOW means execute the missed occurrence now, not rewrite history and pretend the occurrence was scheduled now.

## Existing durable intent wins

A key recovery invariant is preserved.

Suppose:

```text
ExecutionRequest for occurrence 10:00 already exists
Schedule checkpoint still says 10:00
current policy would now SKIP
```

SchedulerEngine does not discard or reinterpret the durable request.

Instead:

```text
existing durable intent
        │
        ▼
reuse request
        │
        ▼
repair Schedule checkpoint
```

Misfire policy only decides whether a new durable intent should be created.

It cannot retroactively revoke an intent that is already durable.

## CATCH_UP and COALESCE foundations

LOT-12 models both future recovery actions:

```python
MisfirePolicy.catch_up(...)
MisfirePolicy.coalesce(...)
```

and the pure evaluator produces:

```text
MisfireDecisionAction.CATCH_UP
MisfireDecisionAction.COALESCE
```

However, the public Scheduler does not yet allow them.

Correct implementation requires explicit backlog reconstruction and bounded selection semantics.

PyScheduleKit refuses to provide a fake partial meaning.

## Public capability boundary

Current public support:

| Policy | Public Scheduler | SchedulerEngine behavior |
|---|---|---|
| RUN_NOW | supported | materialize current occurrence |
| SKIP | supported | advance without request |
| CATCH_UP | modeled, not enabled | isolated without mutation |
| COALESCE | modeled, not enabled | isolated without mutation |

Passing CATCH_UP or COALESCE through:

```python
scheduler.add_schedule(...)
```

fails immediately with a clear validation error.

## Unsupported internal policy isolation

If an internally constructed ScheduleDefinition contains CATCH_UP or COALESCE, SchedulerEngine does not mutate it.

Instead the evaluation result records:

```text
unsupported_policy_schedules
```

This prevents silent skipping, fake catch-up, accidental coalescing, and partial checkpoint advancement.

## SchedulerEngine decision evidence

SchedulerEvaluationResult now includes:

```text
misfire_decisions
```

Each record contains:

```text
OccurrenceKey
MisfireDecision
```

This makes the policy result inspectable without turning logs into authoritative state.

The durable Schedule and ExecutionRequest remain the authoritative state.

## run_pending result

RunPendingResult now also exposes:

```text
unsupported_policy_schedules
```

Under the public Scheduler this should normally remain empty because unsupported recovery modes are rejected at schedule creation.

It exists to preserve observability if lower-level application components are used directly.

## Public API

LOT-12 exposes:

```python
from pyschedulekit import (
    GracePeriod,
    LatenessStatus,
    MisfirePolicy,
    MisfirePolicyAction,
)
```

Example SKIP policy:

```python
scheduler.add_schedule(
    target=task,
    trigger=trigger,
    misfire=MisfirePolicy.skip(
        grace=GracePeriod.seconds(60),
    ),
)
```

Example RUN_NOW policy:

```python
scheduler.add_schedule(
    target=task,
    trigger=trigger,
    misfire=MisfirePolicy.run_now(
        grace=GracePeriod.seconds(30),
    ),
)
```

## End-to-end SKIP example

Given:

```text
next_run_time = 10:10
grace = 0
evaluation_now = 10:15
policy = SKIP
```

the public cycle becomes:

```text
Scheduler.run_pending()
        │
        ▼
Occurrence 10:10
        │
        ▼
MISFIRED
        │
        ▼
SKIP
        │
        ├── no ExecutionRequest
        ├── no Execution
        ├── no Attempt
        └── Schedule checkpoint advances
```

## End-to-end grace example

Given:

```text
next_run_time = 10:10
grace = 10 minutes
evaluation_now = 10:15
policy = SKIP
```

the occurrence is LATE_ELIGIBLE, not MISFIRED.

Therefore:

```text
policy SKIP is not applied
→ ExecutionRequest created
→ Execution
→ Attempt
→ callable
```

## Transactional guarantee

For SKIP:

```text
advance checkpoint
+
commit
```

happens without any request creation.

For RUN_NOW:

```text
create ExecutionRequest
+
advance checkpoint
+
single UnitOfWork commit
```

remains atomic.

LOT-12 does not weaken the LOT-08 durable-intent guarantee.

## What LOT-12 does not do

LOT-12 does not:

- reconstruct multiple missed occurrences in one cycle;
- bound a catch-up batch;
- choose the latest missed occurrence;
- coalesce several occurrences;
- apply concurrency policy;
- retry workload failures;
- alter runtime sleep/wakeup behavior.

These remain separate concerns.

## Qualification scenarios

LOT-12 proves:

- exact scheduled instant is ON_TIME;
- positive lateness inside grace is LATE_ELIGIBLE;
- grace deadline is inclusive;
- strictly after deadline is MISFIRED;
- pre-due classification is rejected;
- SKIP is ignored for ON_TIME;
- SKIP is ignored for LATE_ELIGIBLE;
- SKIP applies to true misfire;
- RUN_NOW materializes true misfire;
- CATCH_UP is a distinct decision;
- COALESCE is a distinct decision;
- policy factories preserve grace;
- default RUN_NOW preserves historical engine behavior;
- SKIP advances without request;
- RUN_NOW preserves original OccurrenceKey;
- skipped DateTrigger completes;
- pre-existing durable request wins over later SKIP;
- unsupported recovery modes do not mutate Schedule state;
- public SKIP prevents workload execution;
- public grace allows slightly late execution;
- public RUN_NOW executes a true misfire;
- public Scheduler rejects CATCH_UP/COALESCE until implemented.

## Architecture progression

```text
Trigger
  │
  ▼
Occurrence
  │
  ▼
LatenessClassifier
  │
  ▼
ON_TIME / LATE_ELIGIBLE / MISFIRED
  │
  ▼
MisfireEvaluator
  │
  ├── MATERIALIZE
  ├── SKIP
  ├── CATCH_UP   [modeled]
  └── COALESCE   [modeled]
```

## Exit criteria

LOT-12 is complete when:

- lateness classification is pure and explicit;
- grace deadline behavior is tested;
- misfire and workload failure remain distinct;
- SKIP and RUN_NOW work end-to-end;
- original occurrence identity survives RUN_NOW;
- existing durable intent cannot be revoked by later policy evaluation;
- unsupported advanced recovery modes fail closed;
- all quality gates are green.

## Next

`LOT-13 — Catch-Up & Coalescing`
