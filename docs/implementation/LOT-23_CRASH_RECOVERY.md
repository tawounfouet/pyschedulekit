# LOT-23 — Crash Recovery

## Goal

Recover durable execution state left behind when a scheduler process stops unexpectedly.

The critical crash shape is:

```text
Execution RUNNING
        +
Attempt RUNNING
        +
process disappears
```

After restart there is no live worker associated with that persisted RUNNING state.

LOT-23 reconciles it before new scheduling work is allowed to begin.

## Recovery boundary

Crash recovery is performed before the first scheduling cycle of one `Scheduler` instance.

```text
Scheduler.run_pending()
        ↓
initial crash recovery
        ↓
recovery complete?
   ┌────┴────┐
   │         │
  yes        no
   │         │
   ▼         ▼
run cycle   CrashRecoveryIncompleteError
```

The same barrier applies before `run_forever()`.

## Public API

Recovery is automatic before the first cycle, and may also be invoked explicitly:

```python
result = scheduler.recover()
```

The most recent result is available through:

```python
scheduler.last_recovery_result
```

## Recovery result

`CrashRecoveryResult` reports:

```text
recovered_execution_ids
retried_execution_ids
failed_execution_ids
cancelled_execution_ids
skipped_execution_ids
errors
remaining_running_execution_ids
complete
```

This makes restart reconciliation observable instead of silently mutating durable state.

## Orphaned RUNNING semantics

LOT-23 currently assumes exclusive runtime ownership of one persistence store.

Without leases or heartbeats, any persisted `RUNNING` Execution discovered during initial restart recovery is considered orphaned.

That assumption is intentionally temporary.

Distributed ownership and fencing belong to later distribution lots.

## Normal crash path

For a RUNNING Execution without a pending cancellation request:

```text
RUNNING Execution
        +
RUNNING Attempt
        ↓
Failure(
    category = UNKNOWN,
    code = execution.crash_recovered,
    retryable_hint = None
)
        ↓
Attempt FAILED
        ↓
RetryEvaluator
        ↓
┌───────────────────────┬────────────────────────┐
│ attempt remains       │ attempts exhausted     │
│                       │                        │
▼                       ▼
RETRY_WAIT              FAILED
next_attempt_at         terminal ExecutionResult
```

Crash recovery never fabricates a successful result.

## Retry semantics

The original `ExecutionPolicySnapshot.retry` is reused.

Crash recovery classifies the failure as `UNKNOWN` and leaves `retryable_hint=None`, so the persisted RetryPolicy remains authoritative. The default policy considers `unknown` retryable, while a custom policy may exclude it.

No special retry configuration is created during recovery.

Example:

```text
Attempt #1 RUNNING
process crashes
restart at 10:01
FixedBackoff = 5 min
        ↓
Attempt #1 FAILED
Execution RETRY_WAIT
next_attempt_at = 10:06
        ↓
10:06
Attempt #2
```

This preserves the same retry semantics used during normal execution.

## Cancellation precedence

A durable cancellation request wins over retry.

If the Execution already contains:

```text
cancellation_requested_at != NULL
```

then recovery performs:

```text
Attempt RUNNING
        ↓
Attempt CANCELLED
        ↓
Execution CANCELLED
        ↓
no retry
```

A process crash therefore cannot erase previously persisted user cancellation intent.

## Consistency checks

A RUNNING Execution must identify a matching RUNNING Attempt.

Recovery refuses to guess when persisted state is structurally inconsistent.

Examples:

```text
RUNNING Execution
but active_attempt_number is NULL

RUNNING Execution
but referenced Attempt does not exist

RUNNING Execution
but referenced Attempt is already terminal
```

These conditions produce explicit `CrashRecoveryError` entries.

## Fail-closed behavior

If any persisted RUNNING state remains unreconciled after the pass:

```text
CrashRecoveryResult.complete == False
```

and the Scheduler raises:

```text
CrashRecoveryIncompleteError
```

New scheduling cycles are not allowed to continue.

This prevents new work from being started while durable execution ownership is ambiguous.

## Concurrency conflicts

Each candidate is reloaded inside its own UnitOfWork before mutation.

If committed state changed between discovery and reconciliation:

```text
PersistenceConflictError
        ↓
candidate skipped
        ↓
remaining RUNNING state detected
        ↓
recovery incomplete
```

A later explicit `recover()` call may retry reconciliation.

## Idempotence

A successfully recovered Execution is no longer RUNNING.

Therefore a second recovery pass does not mutate it again.

```text
first pass
RUNNING → RETRY_WAIT / FAILED / CANCELLED

second pass
not selected
```

## Restart execution path

LOT-23 qualifies the full durable restart flow:

```text
process A
Attempt #1 RUNNING
        ↓
crash
        ↓
process B opens same SQLite database
        ↓
initial recovery
        ↓
Attempt #1 FAILED
Execution RETRY_WAIT
        ↓
backoff expires
        ↓
Attempt #2 RUNNING
        ↓
SUCCESS
```

The Attempt history remains durable and ordered.

## Persistence requirements

The recovery service depends only on persistence ports.

LOT-23 adds:

```text
ExecutionRepository.list_running(limit=...)
```

Both the in-memory and SQLite adapters implement the query.

No SQLite-specific branch exists in the recovery application service.

## Safety properties

1. persisted RUNNING state is reconciled before new work starts;
2. recovery never marks orphaned work successful;
3. the original RetryPolicy controls post-crash retry;
4. cancellation intent has priority over retry;
5. terminal recovery results are persisted atomically with Attempt completion;
6. recovery is idempotent;
7. inconsistent persisted state is surfaced explicitly;
8. incomplete recovery blocks scheduling;
9. every candidate is reloaded before mutation;
10. recovery remains persistence-port driven.

## Qualification

LOT-23 qualifies:

- RUNNING orphan → RETRY_WAIT;
- recovered failure uses `execution.crash_recovered`;
- retry backoff is preserved;
- exhausted retry budget → terminal FAILED;
- persisted cancellation request → CANCELLED;
- second pass idempotence;
- missing active Attempt detection;
- first Scheduler cycle automatically performs recovery;
- incomplete recovery blocks scheduling;
- full SQLite restart → recovery → Attempt #2 → SUCCESS.

## Current ownership assumption

LOT-23 assumes one active scheduler runtime owns a persistence store at a time.

Creating two independent live Scheduler runtimes over the same store can make one runtime mistake the other's RUNNING work for crash residue.

This is intentionally unresolved until distributed coordination introduces claims, leases, and fencing.

## Non-goals

LOT-23 does not implement:

- worker heartbeats;
- execution leases;
- fencing tokens;
- multi-worker ownership;
- distributed crash detection;
- recovery of external side effects;
- exactly-once execution;
- reconciliation of every historical inconsistency;
- outbox delivery.

## Next

`LOT-24 — Reconciliation`
