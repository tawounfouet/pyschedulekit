# LOT-29 — Distributed Scheduler Coordination

## Goal

Coordinate Schedule materialization across multiple Scheduler workers sharing the same durable store.

LOT-26 through LOT-28 already coordinate Execution ownership and concurrency admission. The remaining distributed race is earlier:

```text
worker A sees Schedule due
worker B sees same Schedule due
        ↓
both evaluate the same checkpoint
```

Optimistic concurrency prevented corruption, but normal multi-worker operation could still degrade into repeated persistence conflicts.

LOT-29 replaces that conflict-driven behavior with explicit Schedule-scoped ownership.

## No global scheduler leader

PyScheduleKit does not elect one global scheduler leader for Schedule materialization.

Instead ownership is scoped by `ScheduleId`:

```text
schedule-a → worker A
schedule-b → worker B
schedule-c → worker A or B
```

This preserves horizontal concurrency between independent schedules while guaranteeing one materializer for a given Schedule at a time.

## Schedule materialization lease

LOT-29 introduces:

```text
ScheduleMaterializationLease
├── schedule_id
├── worker_id
├── token
├── generation
├── acquired_at
├── expires_at
├── state
├── released_at
└── version
```

States:

```text
ACTIVE → RELEASED
```

The lease is active while:

```text
now < expires_at
```

A released or expired lease may be reassigned.

Takeover increments the fencing generation.

## Scheduler configuration

The public Scheduler creates a materialization coordinator automatically:

```python
scheduler = Scheduler(
    uow_factory=SqliteUnitOfWorkFactory("scheduler.db"),
    worker_id="worker-a",
    materialization_lease_ttl=Duration.seconds(5),
)
```

Default TTL:

```text
5 seconds
```

The lease protects one Schedule evaluation transaction. It is intentionally shorter-lived than a long-running Execution lease.

## Evaluation flow

For every due Schedule:

```text
discover due ScheduleId
        ↓
acquire ScheduleMaterializationLease
        ↓
reload Schedule
        ↓
evaluate misfire / backlog
        ↓
materialize or reuse ExecutionRequest
        ↓
advance Schedule checkpoint
        ↓
release lease
        ↓
single UnitOfWork commit
```

If another worker owns the active lease, the Schedule is skipped for the current cycle.

The result exposes:

```python
result.materialization_denied_schedule_ids
```

This is not reported as a persistence error.

## Transactional fencing

The most important LOT-29 invariant is that lease release is part of the same transaction as Schedule materialization.

Conceptually:

```text
Schedule checkpoint update
+
ExecutionRequest insert/reuse
+
materialization lease RELEASED
        ↓
same commit
```

Suppose worker A owns generation 4 but stalls.

Worker B takes over after expiry:

```text
generation 4
    ↓ expiry
generation 5
```

If worker A later tries to commit its old staged Schedule/request state, the materialization-lease optimistic version or fencing identity no longer matches.

The entire UnitOfWork rolls back.

Therefore a stale worker cannot advance `next_run_time` or persist a request after ownership moved.

## Deterministic time

LOT-29 preserves the SchedulerEngine rule that one cycle uses one explicit:

```text
evaluation_now
```

Materialization ownership is acquired using that snapshot.

No hidden domain wall-clock read is introduced into Schedule evaluation.

A worker that exceeds its lease only becomes stale when another worker successfully performs an expired takeover. That takeover changes the durable generation/version and fences the original transaction.

## Recovery-limit and no-op paths

The materialization lease is also released transactionally when evaluation produces no business mutation, including:

- Schedule no longer ACTIVE;
- checkpoint no longer due after reload;
- no current occurrence;
- bounded COALESCE cannot prove the true latest occurrence.

This prevents control-plane leases from lingering unnecessarily.

## Independent Schedule parallelism

Ownership is Schedule-scoped rather than global.

Two workers may concurrently own:

```text
worker A → schedule-a
worker B → schedule-b
```

A worker attempting to acquire the other's Schedule receives normal coordination denial.

This avoids turning distributed scheduling into a single-leader bottleneck.

## Ongoing expired Execution recovery

LOT-23 originally ran crash recovery before scheduling after process startup.

LOT-28 made that recovery lease-aware.

LOT-29 makes it ongoing.

Every `run_pending()` cycle performs an opportunistic recovery scan before capturing the new evaluation snapshot:

```text
RUNNING Execution
        ↓
active foreign lease?
   yes ───────→ preserve
   no / expired
        ↓
recovery takeover
        ↓
generation + 1
        ↓
recover Attempt
```

Therefore a worker crash can be recovered by another already-running Scheduler after the Execution lease expires; no process restart is required.

The same behavior applies inside `run_forever()`, because the continuous runtime is built on `RunPendingService`.

Recovery still fails closed when the durable graph is inconsistent.

## Cross-worker wake-up

SQLite does not provide a portable database notification primitive suitable for PyScheduleKit's current persistence port.

LOT-29 therefore preserves bounded wake-up semantics:

```text
next durable deadline
        ↓
WakeUpPlanner
        ↓
max_sleep upper bound
```

A mutation performed by another process may not interrupt a worker's local `EventLoopWaiter` immediately.

The delay is bounded by `max_sleep`.

Push-based cross-worker notification belongs to future database/broker-specific runtime adapters and is not required for scheduling correctness.

## SQLite schema v7

LOT-29 introduces:

```text
SCHEMA_VERSION = 7
```

New table:

```text
schedule_materialization_leases
```

with one row per Schedule:

```text
schedule_id PRIMARY KEY
worker_id
token UNIQUE
acquired_at
expires_at
generation
state
released_at
version
```

The full migration chain is now:

```text
v1 → v2 → v3 → v4 → v5 → v6 → v7
```

## Safety properties

1. only one active materialization lease exists per Schedule;
2. different Schedules remain independently materializable;
3. active ownership is denied to competing workers;
4. expired ownership may be taken over;
5. takeover increments the fencing generation;
6. Schedule checkpoint/request mutation and lease release commit atomically;
7. stale materialization commits roll back completely;
8. coordination contention is observable separately from persistence conflict;
9. already-running schedulers recover expired Execution leases without restart;
10. active foreign Execution leases remain protected.

## Qualification

LOT-29 qualifies:

- materialization-lease domain invariants;
- exact-expiry takeover;
- generation increment;
- active-owner denial;
- independent ownership of different Schedules;
- transactional release with Schedule/request mutation;
- stale-generation rollback of checkpoint and request;
- SQLite repository persistence;
- SQLite v6 → v7 migration;
- legacy migrations reaching v7;
- public Scheduler wiring;
- `RunPendingResult.materialization_denied_schedule_ids`;
- ongoing recovery of an expired foreign Execution lease.

## Distribution phase

```text
LOT-26  Distributed Claims                  ✅
LOT-27  Multi-worker Admission              ✅
LOT-28  Lease / Fencing Refinements         ✅
LOT-29  Distributed Scheduler Coordination  ✅
```

The Distribution phase is now complete for the current SQLite/runtime scope.

## Next

`LOT-30 — Observability`
