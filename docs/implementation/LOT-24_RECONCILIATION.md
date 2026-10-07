# LOT-24 — Reconciliation

## Goal

Detect and repair durable scheduler graph drift that is broader than crash recovery.

LOT-23 answers:

```text
What should happen to orphaned RUNNING work after a crash?
```

LOT-24 answers:

```text
Are ExecutionRequest, Execution, and Attempt records mutually coherent?
```

The two concerns are intentionally separate.

## Startup order

A Scheduler now starts durable work in this order:

```text
Crash Recovery
      ↓
Reconciliation
      ↓
Scheduling
```

Recovery removes orphaned RUNNING ownership first.

Reconciliation then inspects a stable durable graph.

If either phase is incomplete, scheduling fails closed.

## Public API

Reconciliation runs automatically before the first scheduling cycle.

It can also be invoked explicitly:

```python
result = scheduler.reconcile()
```

The latest result remains observable:

```python
scheduler.last_reconciliation_result
```

## Reconciliation result

`ReconciliationResult` exposes:

```text
repaired_request_ids
reconstructed_execution_ids
issues
scanned_requests
scanned_executions
scan_truncated
complete
```

`complete` is true only when:

```text
scan_truncated == False
and
issues == ()
```

## Bounded scans

Reconciliation is deliberately bounded.

Persistence ports expose:

```text
ExecutionRequestRepository.list_for_reconciliation(limit=...)
ExecutionRepository.list_for_reconciliation(limit=...)
```

The service reads `limit + 1` rows to prove whether the requested bound covered the whole graph.

If more durable records exist:

```text
scan_truncated = True
complete = False
```

The Scheduler does not pretend that a partial scan proved global consistency.

## Safe automatic repairs

LOT-24 repairs only divergences for which the durable intent is unambiguous.

### DISPATCHED request without Execution

A request already persisted as `DISPATCHED` expresses that durable execution creation was intended.

If its Execution is missing:

```text
ExecutionRequest DISPATCHED
        +
no Execution
        ↓
reconstruct Execution
```

The reconstructed Execution uses deterministic identities:

```text
ExecutionId.for_request(request.id)
IdempotencyKey.for_request(request.id)
```

and reuses the request's durable:

- target;
- retry policy;
- timeout.

The reconstructed Execution starts in `QUEUED`.

Its `created_at` uses the durable request creation time because the lost admission timestamp cannot be proven.

No fabricated timestamp is introduced.

### Execution exists but request is not DISPATCHED

If an Execution already exists and its request is:

```text
PENDING
or
WAITING_ADMISSION
```

then the existing Execution is stronger evidence that admission already occurred.

Reconciliation performs:

```text
request.mark_dispatched()
```

No new Execution is created.

## Unsafe divergences

Some states admit more than one plausible history.

LOT-24 reports them instead of guessing.

### Terminal request with Execution

```text
DROPPED request + Execution
CANCELLED request + Execution
```

Reconciliation cannot know whether the Execution is the error or the terminal request state is the error.

Result:

```text
reconciliation.terminal_request_has_execution
```

No mutation is applied.

### Execution/request target mismatch

```text
Execution.target != ExecutionRequest.target
```

Result:

```text
reconciliation.execution_target_mismatch
```

### Policy snapshot mismatch

An Execution policy snapshot should correspond to the request from which it was created.

Mismatch produces:

```text
reconciliation.execution_policy_mismatch
```

The service does not rewrite historical execution policy.

## Attempt history checks

For every scanned Execution, LOT-24 validates the durable Attempt history.

### Numbering

Expected:

```text
attempt_count = N

Attempts:
1, 2, ..., N
```

A missing, duplicate, or non-contiguous history produces:

```text
reconciliation.attempt_history_mismatch
```

### RUNNING coherence

A RUNNING Execution must expose exactly one matching RUNNING Attempt.

LOT-23 should normally remove all orphaned RUNNING state before this phase.

If inconsistency remains:

```text
reconciliation.running_attempt_mismatch
```

A non-RUNNING Execution with a RUNNING Attempt produces:

```text
reconciliation.non_running_execution_has_running_attempt
```

### RETRY_WAIT coherence

A RETRY_WAIT Execution must have a latest Attempt in:

```text
FAILED
or
TIMED_OUT
```

Otherwise:

```text
reconciliation.retry_wait_history_mismatch
```

### Terminal coherence

The latest Attempt must agree with the terminal Execution state:

```text
SUCCESS   ↔ SUCCESS
FAILED    ↔ FAILED
CANCELLED ↔ CANCELLED
TIMED_OUT ↔ TIMED_OUT
```

Otherwise:

```text
reconciliation.terminal_history_mismatch
```

LOT-24 reports the divergence rather than rewriting historical results.

## Fail-closed startup

Automatic startup reconciliation behaves as:

```text
reconcile()
    ↓
complete?
 ┌──┴──┐
 │     │
yes    no
 │     │
 ▼     ▼
run   ReconciliationIncompleteError
```

New scheduling work does not begin while global durable consistency is unproven.

## Manual reconciliation guard

`scheduler.reconcile()` cannot run while the local runtime or local Executions are active.

This prevents a consistency pass from inspecting a graph while this Scheduler instance is intentionally mutating it.

## Recovery interaction

Calling `scheduler.recover()` invalidates any prior reconciliation proof.

The next scheduling cycle must reconcile again.

This preserves the ordering:

```text
recovery mutation
      ↓
reconciliation proof
      ↓
new work
```

## Persistence abstraction

Reconciliation remains application-layer logic.

Both adapters implement the bounded scan ports:

```text
InMemoryUnitOfWorkFactory
SqliteUnitOfWorkFactory
```

No SQLite-specific branch exists inside `ReconciliationService`.

## End-to-end repair

LOT-24 qualifies:

```text
DISPATCHED request
+
missing Execution
      ↓
new Scheduler
      ↓
Recovery
      ↓
Reconciliation reconstructs QUEUED Execution
      ↓
run_pending()
      ↓
Attempt #1
      ↓
SUCCESS
```

So reconciliation restores an executable trajectory, not merely a cosmetic database state.

## Safety properties

1. crash recovery runs before reconciliation;
2. reconciliation runs before new scheduling work;
3. scans are bounded and truncation is explicit;
4. partial scans never claim global consistency;
5. deterministic request/execution drift may be repaired;
6. historical ambiguity is reported, not guessed;
7. Execution IDs remain deterministic;
8. Attempt history is never fabricated;
9. terminal results are never rewritten automatically;
10. incomplete reconciliation blocks scheduling.

## Qualification

LOT-24 qualifies:

- DISPATCHED request → missing Execution reconstruction;
- existing Execution → request restored to DISPATCHED;
- terminal request + Execution remains unresolved;
- missing Attempt history detection;
- terminal Attempt/Execution mismatch detection;
- bounded-scan truncation;
- automatic reconciliation before first Scheduler cycle;
- fail-closed startup on unsafe drift;
- reconstruction → normal execution → SUCCESS E2E.

## Current scope

LOT-24 reconciles the persisted execution graph.

It does not yet attempt to reconstruct arbitrary missing Schedule occurrences from historical trigger evaluation beyond the already-qualified SchedulerEngine misfire/catch-up semantics.

It also does not repair external side effects.

## Non-goals

LOT-24 does not implement:

- exactly-once external execution;
- external-system reconciliation;
- worker leases or heartbeats;
- distributed graph ownership;
- automatic deletion of inconsistent history;
- arbitrary historical Attempt reconstruction;
- outbox delivery.

## Next

`LOT-25 — Outbox`
