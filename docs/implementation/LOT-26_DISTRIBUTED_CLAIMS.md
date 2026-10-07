# LOT-26 — Distributed Claims

## Goal

Prevent two Scheduler workers sharing the same durable store from starting the same runnable Execution concurrently.

LOT-26 closes the distributed race between:

```text
worker A reads QUEUED
worker B reads QUEUED
        ↓
both try to start Attempt #1
```

The new flow is:

```text
runnable Execution
        ↓
durable claim acquisition
        ↓
claim owner only
        ↓
Attempt start consumes claim atomically
        ↓
Execution RUNNING
```

## Scope

LOT-26 originally introduced **one-shot execution claims**. LOT-28 refines the same durable entity into a renewable fenced Execution lease while preserving the acquisition semantics established here.

It does not yet implement a renewable lease protocol, long-running heartbeat, generalized fencing token, or global scheduler leadership.

Those are later Distribution concerns.

## Domain model

`ExecutionClaim` contains:

```text
execution_id
worker_id
token
claimed_at
expires_at
state
released_at
version
```

States:

```text
ACTIVE
   ↓ consume/release
RELEASED
```

An active claim is valid only while:

```text
now < expires_at
```

At the exact expiration instant it is no longer active.

## Worker identity

Every Scheduler instance has a stable worker identity for its lifetime.

```python
scheduler = Scheduler(
    uow_factory=SqliteUnitOfWorkFactory("scheduler.db"),
    worker_id="worker-a",
)
```

When omitted, PyScheduleKit creates a random worker ID for that Scheduler instance.

Public inspection:

```python
scheduler.worker_id
```

## Claim TTL

The claim acquisition window is bounded:

```python
Scheduler(
    worker_id="worker-a",
    claim_ttl=Duration.seconds(30),
)
```

The default is 30 seconds.

This TTL protects the hand-off from runnable state to Attempt start.

It is not yet a renewable long-running execution lease.

## Acquisition

Before `ExecutionRunner` starts work, `RunPendingService` calls:

```text
ExecutionClaimCoordinator.acquire()
```

The coordinator verifies that the Execution is still runnable:

```text
QUEUED

or

RETRY_WAIT
and next_attempt_at <= now
```

Then it either:

- inserts a new claim;
- takes over an expired/released claim;
- denies acquisition while another active claim exists.

Expected contention is not reported as a business error.

`RunPendingResult.claim_denied_execution_ids` exposes the skipped Executions.

## Durable arbitration

Claims are persisted in the shared UnitOfWork:

```text
uow.schedules
uow.requests
uow.executions
uow.attempts
uow.claims
uow.outbox
```

SQLite uniqueness provides one durable claim row per Execution:

```text
execution_claims.execution_id PRIMARY KEY
```

The token is also unique.

Concurrent insert/update races are converted into normal claim denial through persistence conflict handling.

## One-shot claim consumption

The most important LOT-26 invariant is that obtaining a claim is not enough.

The worker must still prove ownership at Attempt start.

`ExecutionService.start_attempt(...)` receives an `ExecutionClaimHandle` and, inside the same UnitOfWork:

1. reloads the claim;
2. verifies the Execution ID;
3. verifies the claim is still active;
4. verifies worker ID and token ownership;
5. transitions the claim to RELEASED;
6. transitions the Execution to RUNNING;
7. creates Attempt N;
8. creates the outbox `execution.attempt.started` message;
9. commits all mutations atomically.

Conceptually:

```text
ACTIVE claim
+
QUEUED Execution
        ↓ one transaction
RELEASED claim
+
RUNNING Execution
+
RUNNING Attempt
+
outbox message
```

This prevents a stale worker from starting after its claim was taken over.

## Expired takeover

An expired claim may be reassigned:

```text
worker A claim
expires_at = 10:00:30
        ↓
10:00:30
        ↓
worker B may acquire
```

Reassignment changes:

- worker ID;
- token;
- acquisition timestamp;
- expiry timestamp;
- optimistic version.

If worker A later tries to start with its old handle, ownership validation fails.

## Optimistic concurrency

Claim updates use the same CAS pattern as the rest of durable persistence:

```sql
UPDATE execution_claims
SET ...
WHERE execution_id = ?
  AND version = ?
```

Therefore two workers attempting expired takeover cannot both win.

## In-memory adapter

The in-memory adapter implements the same claim repository and optimistic semantics.

It remains process-local, so it is useful for contract and unit testing but does not provide inter-process distribution by itself.

## SQLite schema v4

LOT-26 introduces:

```text
SCHEMA_VERSION = 4
```

and:

```text
execution_claims
```

Schema transitions:

```text
new database → v4
v3 database  → v4
v2 database  → v3 → v4
v1 database  → v2 → v3 → v4
```

Existing scheduler/outbox data remains intact.

## Failure before Attempt start

If claim acquisition succeeds but target preparation or another pre-start control-plane step fails, `RunPendingService` performs a best-effort explicit release.

If the process crashes before release, TTL expiration makes the claim reclaimable.

## Failure after Attempt start

Once Attempt start commits:

```text
claim RELEASED
Execution RUNNING
Attempt RUNNING
```

The claim is no longer the ownership mechanism.

Existing durable RUNNING state and LOT-23 crash recovery remain responsible for interrupted work.

LOT-26 therefore protects **start admission**, not long-running worker liveness.

## Safety properties

1. only one active claim exists per Execution;
2. active claims cannot be reassigned before expiry;
3. expired claims may be taken over;
4. claim tokens are opaque and unique;
5. stale worker/token ownership is rejected;
6. Attempt start consumes the claim atomically;
7. claim consumption and Execution RUNNING state commit together;
8. persistence conflicts fail closed to claim denial;
9. normal contention is observable but not treated as a business failure;
10. SQLite and in-memory adapters implement the same claim contract.

## Qualification

LOT-26 qualifies:

- active claim semantics;
- exact-expiry takeover;
- wrong-owner release rejection;
- idempotent owner release;
- one active winner across two workers;
- expired takeover by a second worker;
- stale handle rejected at Attempt start;
- winning handle consumed atomically;
- SQLite v3 → v4 migration;
- legacy migrations reaching current schema;
- Scheduler worker identity and claim-aware run path.

## Non-goals

LOT-26 does not implement:

- renewable execution leases;
- claim heartbeat;
- distributed fencing across arbitrary external side effects;
- distributed concurrency admission limits;
- scheduler leader election;
- worker membership;
- worker health registry;
- distributed wake-up coordination.

## Distribution roadmap

```text
LOT-26  Distributed Claims                 ✅
LOT-27  Multi-worker Admission             ⏭ NEXT
LOT-28  Lease / Fencing Refinements         ⬜
LOT-29  Distributed Scheduler Coordination  ⬜
```

## Next

`LOT-27 — Multi-worker Admission`
