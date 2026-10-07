# LOT-28 — Lease / Fencing Refinements

## Goal

Extend LOT-26 Execution claims and LOT-27 Schedule admission locks into stale-owner-safe coordination primitives.

LOT-28 adds two guarantees:

1. a RUNNING Attempt keeps an active renewable Execution lease until completion;
2. every takeover increments a monotonic fencing generation so an old owner can no longer commit scheduler state after ownership has moved.

## Execution lease

LOT-26 originally protected only the transition into RUNNING:

```text
QUEUED
  ↓
ExecutionClaim ACTIVE
  ↓
Attempt start
  ↓
claim RELEASED
  ↓
RUNNING
```

LOT-28 changes this to:

```text
QUEUED / due RETRY_WAIT
        ↓
acquire generation N
        ↓
Attempt RUNNING
+
lease ACTIVE generation N
        ↓
heartbeat renewals
        ↓
Attempt terminal / RETRY_WAIT
+
lease RELEASED
        ↓
same transaction
```

The claim is no longer consumed at Attempt start.

## Monotonic fencing generation

`ExecutionClaim` now contains:

```text
execution_id
worker_id
token
generation
claimed_at
expires_at
state
released_at
version
```

Generation starts at 1.

A renewal preserves it:

```text
generation N
    ↓ renew
generation N
```

A takeover increments it:

```text
generation N expired
        ↓
new owner
        ↓
generation N + 1
```

The opaque token identifies one concrete ownership acquisition while generation provides a monotonic fencing value.

## Attempt start fencing

`ExecutionService.start_attempt()` now keeps the lease ACTIVE.

Inside the same UnitOfWork it:

1. reloads the Execution and lease;
2. validates worker, token and generation;
3. performs a versioned lease touch;
4. transitions the Execution to RUNNING;
5. creates the RUNNING Attempt;
6. creates `execution.attempt.started`;
7. commits all writes atomically.

A takeover between lease load and commit makes the lease CAS fail, rolling back the whole Attempt-start transaction.

## Lease heartbeat

`ExecutionRunner` starts an `ExecutionLeaseHeartbeat` once the Attempt is durable RUNNING.

Default Scheduler configuration:

```python
Scheduler(
    claim_ttl=Duration.seconds(30),
    lease_heartbeat_interval=Duration.seconds(10),
)
```

When the heartbeat interval is omitted:

```text
heartbeat_interval = claim_ttl / 3
```

Invariant:

```text
0 < heartbeat_interval < claim_ttl
```

Each heartbeat reloads the lease, verifies the fencing identity, extends `expires_at` to `now + claim_ttl`, and saves with optimistic CAS.

Renewal keeps the same generation.

If renewal fails, the local runner marks ownership as lost and refuses terminal persistence.

## Fenced completion

All Attempt completion paths accept the current claim handle:

- success;
- failure;
- timeout;
- cancellation.

Before mutating the Attempt or Execution, the service verifies and releases the lease.

The following are then committed together:

```text
lease RELEASED
+
Attempt terminal state
+
Execution terminal / RETRY_WAIT state
+
execution.attempt.completed outbox
```

A stale worker therefore gets:

```text
ClaimOwnershipError
```

and cannot overwrite current scheduler state.

## Pre-start failures

Target resolution and other control-plane failures that happen before Attempt start explicitly release the acquired lease.

Once the Attempt has reached RUNNING, generic `run_pending()` cleanup no longer releases ownership.

That distinction preserves crash evidence:

```text
pre-start failure
→ release

RUNNING + crash/conflict
→ lease remains until expiry/recovery
```

## External fencing token

The Executor port now accepts:

```python
fencing_token: int | None
```

Trusted Python callables may request it explicitly:

```python
def job(*, fencing_token: int) -> None: ...
```

or combine it with cooperative cancellation:

```python
def job(
    *,
    cancellation_token,
    fencing_token: int,
) -> None: ...
```

For Scheduler-managed distributed execution, this value is the current Execution lease generation.

An external sink that supports fencing can enforce:

```text
accept only generations >= last_seen_generation
```

PyScheduleKit exposes the token but cannot force arbitrary external systems to honor it.

## Lease-aware crash recovery

LOT-23 recovery is refined for multiple live workers.

```text
RUNNING
  ↓
active lease?
 ┌───────┴──────────┐
yes                  no / expired
 │                        │
 ▼                        ▼
PROTECTED             recovery takeover
                           │
                    generation + 1
                           │
                           ▼
                    recover Attempt
```

A second Scheduler therefore does not recover work still actively owned by another worker.

`CrashRecoveryResult` now exposes:

```python
protected_execution_ids
```

Protected RUNNING Executions do not make the recovery pass incomplete.

If recovery takes ownership and later encounters an inconsistent durable graph, its temporary recovery lease is best-effort released so the inconsistency remains visible and fail-closed.

## Stale worker after recovery

Example:

```text
worker A
generation 4
RUNNING
   │
lease expires
   ▼
worker B recovery takeover
generation 5
   │
Attempt recovered
   │
lease RELEASED generation 5

worker A returns late
generation 4
   │
tries terminal write
   ▼
ClaimOwnershipError
```

The old worker cannot overwrite the recovered result.

## Admission fencing

LOT-27 Schedule admission locks also gain a monotonic generation.

More importantly, the admission decision and lock release now commit in the same UnitOfWork:

```text
load lock generation N
+
count active Executions
+
stage ADMIT / QUEUE / DROP
+
release generation N
        ↓
single commit
```

If another worker takes over as generation N+1 before the stale transaction commits:

```text
lock CAS fails
        ↓
whole UnitOfWork rolls back
        ↓
no stale ADMIT / QUEUE / DROP
```

This closes the TTL-overrun race left by LOT-27.

## SQLite schema v6

LOT-28 introduces:

```text
SCHEMA_VERSION = 6
```

New columns:

```text
execution_claims.generation
schedule_admission_locks.generation
```

Both are non-null integers constrained to values >= 1.

Migration:

```text
v5 → v6
```

Existing rows receive generation 1.

The complete migration chain is:

```text
v1 → v2 → v3 → v4 → v5 → v6
```

Historical v4 and v5 schema definitions remain unchanged; generation is introduced only by the v6 migration.

## Safety properties

1. a Scheduler-managed RUNNING Attempt retains active lease ownership;
2. renewal never changes fencing generation;
3. takeover always increments generation;
4. stale generation cannot start or finalize work;
5. Attempt completion and lease release are atomic;
6. heartbeat loss fences the local worker from terminal persistence;
7. active leases protect RUNNING work from crash recovery;
8. recovery takeover fences the previous owner;
9. admission decisions are fenced by admission-lock CAS;
10. fencing generation is available to trusted workloads.

## Qualification

LOT-28 qualifies:

- generation starts at 1;
- takeover increments generation;
- renewal preserves generation;
- stale generation rejection;
- lease remains ACTIVE after Attempt start;
- successful completion releases the lease;
- heartbeat renews a live workload lease;
- local callable receives its fencing token;
- active lease protects RUNNING from recovery;
- expired recovery takeover increments generation;
- stale post-recovery completion is rejected;
- stale admission generation rolls back business writes;
- SQLite v5 → v6 migration;
- legacy migrations reach schema v6.

## Scope boundary

LOT-28 does not yet implement:

- leader election;
- worker membership registry;
- distributed ownership of Schedule materialization;
- cross-worker wake-up notifications;
- periodic expired-lease scavenging across already-running scheduler loops;
- fencing enforcement inside arbitrary external systems.

The scheduler-coordination concerns belong to LOT-29.

## Distribution roadmap

```text
LOT-26  Distributed Claims                  ✅
LOT-27  Multi-worker Admission              ✅
LOT-28  Lease / Fencing Refinements         ✅
LOT-29  Distributed Scheduler Coordination  ✅
```

## Next

`LOT-30 — Observability`
