# LOT-09 — ExecutionRequest & Execution Lifecycle

## Goal

Model the complete lifecycle boundary between a durable scheduling intent and the concrete attempts that execute it.

LOT-09 introduces three distinct state machines:

```text
ExecutionRequest
      │
      ▼
  Execution
      │
      ▼
   Attempt
```

These concepts must never collapse into one object.

## Core distinction

```text
Occurrence
≠
ExecutionRequest
≠
Execution
≠
Attempt
```

An Occurrence is a temporal fact.

An ExecutionRequest is durable intent.

An Execution is one logical run.

An Attempt is one concrete try within that run.

## ExecutionRequest lifecycle

States:

```text
PENDING
   │
   ├── wait_for_admission()
   ▼
WAITING_ADMISSION
   │
   └── mark_dispatched()
   ▼
DISPATCHED
```

Cancellation is allowed from:

```text
PENDING
WAITING_ADMISSION
```

and leads to:

```text
CANCELLED
```

`DISPATCHED` and `CANCELLED` are terminal request states.

## Read-only request identity and payload

These values remain externally immutable:

- RequestId;
- OccurrenceKey;
- TargetRef;
- created_at.

Only the lifecycle state changes through explicit methods.

## Request version

ExecutionRequest now tracks an internal monotonic version.

Every real state transition increments it.

Idempotent repetition of the same terminal transition does not.

This enables optimistic persistence without exposing a premature public version contract.

## Execution lifecycle

States:

```text
QUEUED
  │
  ▼
RUNNING
  │
  ├── SUCCESS
  ├── FAILED
  ├── TIMED_OUT
  ├── CANCELLED
  └── RETRY_WAIT
          │
          ▼
       RUNNING
```

LOT-09 models `RETRY_WAIT` structurally but does not decide retry policy.

LOT-16 will decide whether a Failure should actually schedule another Attempt.

## Attempt lifecycle

An Attempt begins only in:

```text
RUNNING
```

and terminates exactly once as:

```text
SUCCESS
FAILED
TIMED_OUT
CANCELLED
```

A terminal Attempt cannot transition again.

## One Execution, many Attempts

Automatic retry preserves:

```text
ExecutionId
IdempotencyKey
RequestId
TargetRef snapshot
```

and creates:

```text
Attempt #1
Attempt #2
Attempt #3
...
```

Therefore:

> Retry never creates a new Occurrence and never creates a new logical Execution.

## Attempt numbering

Attempt numbers are one-based:

```text
1
2
3
...
```

AttemptId is deterministically derived from:

```text
ExecutionId + AttemptNumber
```

The persistence adapter also enforces uniqueness for:

```text
(execution_id, attempt_number)
```

## IdempotencyKey

Every Execution receives a stable IdempotencyKey derived from its RequestId.

The same key survives every Attempt.

This gives downstream executors one stable logical execution identity for future idempotency support.

## ExecutionPolicySnapshot

LOT-09 introduces a minimal immutable policy snapshot.

Current field:

```text
timeout
```

Retry policy is deliberately not embedded yet.

The snapshot boundary exists now so later policy changes on a Schedule cannot silently rewrite the semantics of an already-created Execution.

## Failure model

LOT-09 introduces a normalized Failure Value Object:

```text
Failure
├── category
├── code
├── message
├── occurred_at
├── retryable_hint
└── details
```

Categories:

- TRANSIENT;
- PERMANENT;
- TIMEOUT;
- CANCELLED;
- UNKNOWN.

A Failure is data.

It is not a Python exception and does not itself decide retryability.

## AttemptResult

Each terminal Attempt owns exactly one immutable AttemptResult.

Rules:

```text
SUCCESS
→ no Failure

FAILED / TIMED_OUT / CANCELLED
→ Failure required
```

## ExecutionResult

ExecutionResult exists only for a terminal Execution.

States:

```text
SUCCESS
FAILED
TIMED_OUT
CANCELLED
```

A `RETRY_WAIT` Execution has no terminal ExecutionResult.

## Active Attempt invariant

At most one Attempt may be active for one Execution.

The Execution stores:

```text
attempt_count
active_attempt_number
```

When RUNNING:

```text
active_attempt_number != None
```

Outside RUNNING:

```text
active_attempt_number == None
```

## Retry-wait invariant

When:

```text
state == RETRY_WAIT
```

then:

```text
next_attempt_at != None
```

A new Attempt cannot start before that Instant.

## Cancellation

Queued or retry-waiting Execution may be cancelled directly.

A RUNNING Execution is not cancelled independently of its active Attempt.

Instead:

```text
Attempt → CANCELLED
then
Execution → CANCELLED
```

This avoids contradictory state where the parent is terminal while a child Attempt remains RUNNING.

## ExecutionService

LOT-09 adds an application service coordinating transactional lifecycle changes.

Operations:

- dispatch request;
- start Attempt;
- succeed Attempt;
- fail Attempt;
- timeout Attempt;
- cancel Attempt;
- cancel queued/retry-waiting Execution.

The service does not invoke workload code.

## Dispatch atomicity

Dispatch performs:

```text
ExecutionRequest
PENDING / WAITING_ADMISSION
      │
      ▼
DISPATCHED

+

create Execution(QUEUED)

+

single UnitOfWork commit
```

The request cannot become durably DISPATCHED without the corresponding Execution being durable in the same transaction.

## Dispatch idempotence

A request already DISPATCHED returns its existing Execution.

The persistence layer enforces:

```text
one Execution per RequestId
```

## Persistence expansion

The UnitOfWork now owns four repositories:

```text
ScheduleRepository
ExecutionRequestRepository
ExecutionRepository
AttemptRepository
```

Commit validates every repository before applying any write.

This preserves all-or-nothing semantics across the complete lifecycle boundary.

## Optimistic versions

Mutable lifecycle entities use internal versions:

```text
ExecutionRequest.version
Execution.version
Attempt.version
```

Repositories remember the version observed at load time and reject stale writes.

## Persistence uniqueness

The in-memory adapter enforces:

```text
OccurrenceKey → one ExecutionRequest

RequestId → one Execution

ExecutionId + AttemptNumber → one Attempt
```

## Deferred Schedule acceptance criteria now closed

LOT-05 intentionally deferred:

- T-SCH-012;
- T-SCH-013;
- T-SCH-014.

LOT-09 now proves:

### T-SCH-012

Rescheduling a Schedule does not modify an already-created Execution.

### T-SCH-013

Pausing a Schedule does not cancel an existing Execution.

### T-SCH-014

Cancelling a Schedule does not cancel an existing Execution.

Scheduling lifecycle and execution lifecycle are now demonstrably independent.

## LOT-09 execution qualification

The test suite covers:

- request initial PENDING state;
- WAITING_ADMISSION transition;
- DISPATCHED transition;
- request cancellation;
- QUEUED Execution creation;
- Execution requires dispatched request;
- start Attempt;
- one-active-Attempt invariant;
- successful Attempt → successful Execution;
- failed Attempt → failed Execution;
- failed Attempt → RETRY_WAIT;
- same ExecutionId across retry;
- same IdempotencyKey across retry;
- increasing AttemptNumber;
- retry cannot start before retry_at;
- timeout outcome;
- queued cancellation;
- running cancellation through active Attempt;
- Attempt cannot complete twice;
- foreign Attempt rejected;
- policy snapshot retained;
- dispatch persistence;
- dispatch idempotence;
- Attempt persistence;
- terminal result persistence;
- retry path persistence;
- T-SCH-012/013/014.

## Intentionally deferred

LOT-09 does not:

- call Python functions;
- resolve TargetRef;
- classify arbitrary Python exceptions;
- automatically choose retry;
- evaluate concurrency policy;
- execute timeouts;
- run worker threads.

Those belong to later lots.

## Architecture progression

```text
SchedulerEngine
      │
      ▼
ExecutionRequest
      │
      ▼
ExecutionService.dispatch()
      │
      ▼
Execution QUEUED
      │
      ▼
Attempt RUNNING
      │
      ▼
AttemptResult
      │
      ▼
ExecutionResult
```

## Exit criteria

LOT-09 is complete when:

- request, execution and attempt state machines are explicit;
- one Execution maps to one RequestId;
- one Execution may own multiple Attempts;
- only one Attempt is active at a time;
- terminal results are immutable;
- retries preserve ExecutionId and IdempotencyKey;
- persistence updates are optimistic and atomic;
- Schedule lifecycle cannot mutate existing Executions;
- all quality gates are green.

## Next

`LOT-10 — Local Executor`
