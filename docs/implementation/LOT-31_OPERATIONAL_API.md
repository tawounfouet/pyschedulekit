# LOT-31 — Operational API

## Goal

Expose a stable operational control surface for running PyScheduleKit instances without leaking mutable domain aggregates or persistence repositories.

LOT-31 answers a different question from LOT-30:

```text
LOT-30 Observability
    What is the scheduler doing?

LOT-31 Operational API
    What state is it in, and what may an operator safely do?
```

The first operational API is a Python contract. HTTP, CLI, Kubernetes probes, and administration UIs remain adapters.

## Boundary

The public facade becomes:

```text
Operator / Adapter
       │
       ▼
    Scheduler
       │
       ├── immutable inspection snapshots
       ├── transactional Schedule controls
       ├── health
       └── readiness
              │
              ▼
      SchedulerOperations
              │
              ▼
          UnitOfWork
```

Repositories remain internal implementation details.

## Immutable Schedule inspection

```python
snapshot = scheduler.inspect_schedule("billing-refresh")
```

returns `ScheduleSnapshot`:

```text
ScheduleSnapshot
├── schedule_id
├── state
├── revision
├── persistence_version
├── next_run_time
├── target_kind
├── target_reference
├── timezone
└── timeout_seconds
```

The returned object is immutable and detached from the UnitOfWork identity map.

An operator cannot accidentally mutate durable scheduler state by modifying an inspected object.

## Immutable Execution inspection

```python
snapshot = scheduler.inspect_execution(execution_id)
```

returns `ExecutionSnapshot`:

```text
ExecutionSnapshot
├── execution_id
├── request_id
├── state
├── created_at
├── attempt_count
├── active_attempt_number
├── next_attempt_at
├── cancellation_requested_at
├── is_terminal
├── target_kind
├── target_reference
├── failure_category
├── failure_code
└── completed_at
```

Exception messages and arbitrary failure details are intentionally not copied into this base operational view.

## Explicit not-found semantics

Operational lookup failures use explicit public exceptions:

```text
ScheduleNotFoundError
ExecutionNotFoundError
```

String identities accepted by the public Scheduler are normalized to the existing domain identity types before entering the application service.

## Schedule controls

LOT-31 exposes:

```python
scheduler.pause_schedule(schedule_id)
scheduler.resume_schedule(schedule_id)
scheduler.cancel_schedule(schedule_id)
```

Each command:

1. opens a UnitOfWork;
2. loads the Schedule aggregate;
3. invokes the existing domain transition;
4. saves the aggregate;
5. commits atomically;
6. returns an immutable post-commit snapshot;
7. wakes the local continuous runtime.

No control method edits persistence rows directly.

## Pause semantics

```text
ACTIVE
  │
  └── pause_schedule()
          ↓
       PAUSED
```

Pausing clears `next_run_time` and prevents future occurrence materialization.

Existing ExecutionRequests or Executions are not cancelled.

## Resume semantics

Resume is explicitly time-relative:

```text
Scheduler Clock.now()
        ↓
Schedule.resume(reference=now)
        ↓
Trigger.next_after(now)
        ↓
new next_run_time
```

Paused time is not silently replayed.

This preserves the LOT-05 Schedule aggregate semantics and the project-wide rule that time dependencies are explicit.

## Cancel Schedule semantics

```text
ACTIVE / PAUSED
      │
      └── cancel_schedule()
              ↓
          CANCELLED
```

Schedule cancellation stops future materialization.

It does not imply cancellation of already-created Executions. Execution cancellation remains the separate:

```python
scheduler.cancel_execution(execution_id)
```

control.

## Health

```python
health = scheduler.health()
```

returns `SchedulerHealth`:

```text
healthy
worker_id
persistence_available
runtime_running
shutdown_requested
active_execution_count
cycles_completed
```

Health is liveness-oriented.

The current health rule is:

```text
healthy = persistence_available
```

A graceful shutdown may therefore still be healthy while intentionally not ready.

The persistence probe opens a UnitOfWork and performs a read-only scheduling-horizon query. It does not commit or mutate durable state.

## Readiness

```python
readiness = scheduler.readiness()
```

returns `SchedulerReadiness`:

```text
ready
persistence_available
recovered
reconciled
shutdown_requested
```

Readiness is stricter:

```text
ready =
    persistence_available
    AND crash recovery complete
    AND durable reconciliation complete
    AND shutdown not requested
```

A newly constructed Scheduler is healthy but not yet ready.

After the startup barriers complete through `run_pending()`, `run_forever()`, or explicit recovery/reconciliation, it becomes ready.

After graceful shutdown begins, readiness becomes false.

## Why health and readiness are separate

```text
healthy = process/store can operate

ready = safe to accept scheduling work
```

This distinction maps naturally to service orchestration systems:

- liveness probes should not restart a healthy process merely because it is draining;
- readiness probes should remove a draining or not-yet-reconciled worker from new traffic.

LOT-31 does not embed Kubernetes-specific code.

## Durable behavior

Operational Schedule controls use the same persistence abstraction as the scheduler itself.

SQLite qualification proves:

```text
Scheduler A
   ↓ pause
SQLite
   ↓ restart
Scheduler B
   ↓ inspect
PAUSED
   ↓ resume at explicit Clock
SQLite
   ↓ restart
Scheduler C
   ↓ inspect
ACTIVE with recalculated checkpoint
```

Operational control is therefore durable rather than process-local.

## No embedded HTTP server

LOT-31 deliberately does not add:

- FastAPI;
- Flask;
- aiohttp;
- REST routing;
- authentication middleware;
- web-server lifecycle management.

Those concerns are deployment adapters.

The core contract remains usable from:

```text
Python API
CLI
REST adapter
admin application
worker control plane
Kubernetes probes
tests
```

without making any one transport mandatory.

## Safety properties

1. inspection never returns mutable repository aggregates;
2. inspection is read-only;
3. Schedule controls use aggregate methods, not direct row mutation;
4. Schedule controls commit atomically;
5. resume time comes from the explicit Scheduler Clock;
6. Schedule cancellation does not cancel existing Executions;
7. operational mutations wake the local runtime;
8. persistence health probing is non-mutating;
9. readiness fails closed until recovery and reconciliation complete;
10. graceful shutdown makes readiness false without making liveness false;
11. SQLite restart preserves operational mutations;
12. the core remains transport-neutral.

## Qualification

LOT-31 qualifies:

- immutable Schedule inspection;
- immutable Execution inspection;
- explicit missing-resource errors;
- pause persistence;
- resume checkpoint recalculation from explicit Clock;
- Schedule cancellation persistence;
- non-mutating persistence probing;
- public string identity normalization;
- liveness/readiness separation;
- startup readiness barrier;
- shutdown readiness behavior;
- SQLite restart durability.

## Production maturity roadmap

```text
LOT-30  Observability            ✅
LOT-31  Operational API          ✅
LOT-32  Retention / Cleanup     ⏭ NEXT
LOT-33  Additional Executors     ⬜
LOT-34  Public API Hardening     ⬜
```

## Next

`LOT-32 — Retention / Cleanup`
