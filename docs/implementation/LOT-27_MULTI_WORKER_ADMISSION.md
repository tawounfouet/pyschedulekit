# LOT-27 — Multi-worker Admission

## Goal

Enforce Schedule concurrency limits across multiple Scheduler workers sharing the same durable store.

LOT-14 introduced the policy:

```text
active_instances
      ↓
ConcurrencyEvaluator
      ↓
ADMIT / QUEUE / DROP
```

but serialized count-and-admit only with a process-local `RLock`.

LOT-27 makes that decision globally serialized per Schedule. LOT-28 further fences the decision by committing lock release and ADMIT/QUEUE/DROP atomically under a monotonic generation.

## Race closed

Before LOT-27:

```text
worker A counts 0
worker B counts 0
worker A admits
worker B admits
        ↓
max_instances=1 violated
```

With LOT-27:

```text
worker A
  ↓
ScheduleAdmissionLock(shared)
  ↓
count = 0
  ↓
ADMIT + commit
  ↓
release

worker B
  ↓
acquire same Schedule lock
  ↓
count = 1
  ↓
QUEUE / DROP
```

## Separate responsibilities

LOT-26 ExecutionClaim:

```text
Who may start this Execution?
```

LOT-27 ScheduleAdmissionLock:

```text
Who may perform count-and-admit for this Schedule?
```

They are intentionally separate durable coordination primitives.

## Model

`ScheduleAdmissionLock` contains:

```text
schedule_id
worker_id
token
acquired_at
expires_at
state
released_at
version
```

States:

```text
ACTIVE → RELEASED
```

The lock is active while:

```text
now < expires_at
```

Expired locks may be reassigned.

## Scheduler configuration

The normal Scheduler path uses durable admission locking automatically.

```python
scheduler = Scheduler(
    uow_factory=SqliteUnitOfWorkFactory("scheduler.db"),
    worker_id="worker-a",
    admission_lock_ttl=Duration.seconds(5),
)
```

Default admission lock TTL:

```text
5 seconds
```

This is intentionally short because it protects only the count-and-admit control-plane operation.

## Admission flow

```text
ExecutionRequest
      ↓
resolve ScheduleId
      ↓
acquire ScheduleAdmissionLock
      ↓
reload request
      ↓
count non-terminal Executions
      ↓
ConcurrencyEvaluator
      ↓
ADMIT / QUEUE / DROP
      ↓
commit durable result
      ↓
release lock
```

If another worker owns the active lock, the request is not mutated.

The current cycle reports technical contention through:

```python
result.admission_lock_denied_request_ids
```

This is distinct from:

```python
result.queued_request_ids
```

which represents a real policy decision.

## Persistence

The UnitOfWork now exposes:

```text
uow.admission_locks
```

Both adapters implement the same repository contract.

SQLite stores one row per Schedule:

```text
schedule_admission_locks.schedule_id PRIMARY KEY
```

and a unique opaque token.

Optimistic versioning protects reassignment/release races.

## SQLite schema v5

LOT-27 introduces:

```text
SCHEMA_VERSION = 5
```

with:

```text
schedule_admission_locks
```

Migration chain:

```text
new DB → v5
v4     → v5
v3     → v4 → v5
v2     → v3 → v4 → v5
v1     → v2 → v3 → v4 → v5
```

## Crash behavior

If a worker crashes while holding an admission lock:

```text
ACTIVE lock
      ↓
no release
      ↓
TTL expires
      ↓
another worker may reassign
```

A crash after admission commit but before release may temporarily delay subsequent admissions, but cannot create an over-admission.

## Fallback compatibility

Direct constructions of `ConcurrencyCoordinator` without a durable admission lock coordinator retain the historical process-local `RLock`.

The public `Scheduler` injects the durable coordinator, so normal durable multi-worker operation uses the distributed path.

## Safety properties

1. one active admission lock per Schedule;
2. different Schedules remain independently admissible;
3. active lock cannot be reassigned before expiry;
4. expired lock may be recovered;
5. count-and-admit runs only for the lock owner;
6. contention does not mutate the request;
7. contention is not misreported as a policy QUEUE;
8. global non-terminal count remains authoritative;
9. SQLite CAS protects takeover/release races;
10. max_instances remains valid across cooperating Scheduler workers.

## Qualification

LOT-27 qualifies:

- admission-lock domain invariants;
- active-owner protection;
- exact-expiry takeover;
- SQLite repository persistence;
- two concurrent workers against max_instances=1;
- exactly one admitted Execution during the race;
- lock contention leaves the losing request unmutated;
- a later retry evaluates the policy and enters WAITING_ADMISSION;
- exactly one non-terminal Execution;
- active lock denial without request mutation;
- expired lock recovery;
- SQLite v4 → v5 migration;
- legacy migrations reaching schema v5;
- Scheduler integration with durable lock coordination.

## Non-goals

LOT-27 does not yet implement:

- renewable admission leases;
- fencing generations;
- long-running execution leases;
- global leader election;
- distributed schedule materialization ownership;
- distributed wake-up signaling.

## Distribution roadmap

```text
LOT-26  Distributed Claims                  ✅
LOT-27  Multi-worker Admission              ✅
LOT-28  Lease / Fencing Refinements         ⏭ NEXT
LOT-29  Distributed Scheduler Coordination  ⬜
```

## Next

`LOT-28 — Lease / Fencing Refinements`
