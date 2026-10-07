# LOT-32 — Retention / Cleanup

## Goal

Bound historical scheduler growth without deleting state that can still affect correctness.

> Cleanup may delete immutable history, never live scheduling state.

LOT-32 introduces an explicit retention policy, a bounded cleanup transaction, SQLite retention indexes, and safety qualification across in-memory and durable persistence.

## Public API

```python
from pyschedulekit import RetentionPolicy

result = scheduler.cleanup(
    RetentionPolicy.days(
        execution_history=30,
        published_outbox=14,
    ),
    limit=1000,
)
```

Cleanup is manual and explicit. It is not silently attached to `run_pending()` or the continuous runtime.

## Eligible execution history

One terminal graph is:

```text
ExecutionRequest(DISPATCHED)
        │
        ▼
Execution(terminal)
        │
        ├── Attempt(s)
        └── ExecutionClaim
```

An Execution is eligible only when its state is SUCCESS, FAILED, CANCELLED, or TIMED_OUT and `completed_at < execution_cutoff`.

Deletion order is:

```text
Attempts
   ↓
ExecutionClaim
   ↓
Execution
   ↓
ExecutionRequest
```

## Orphan terminal requests

`DROPPED` and `CANCELLED` requests without an Execution are eligible when `created_at < execution_cutoff`. `PENDING` and `WAITING_ADMISSION` requests are never eligible.

## Outbox retention

Only `PUBLISHED` messages with `published_at < outbox_cutoff` may be deleted. `PENDING` messages are never cleanup candidates, preserving LOT-25 at-least-once delivery.

## Schedules and coordination

LOT-32 never deletes Schedule aggregates. Admission locks and materialization leases are one-row-per-Schedule generation records and do not create unbounded row growth. Execution claims are removed only with a terminal Execution graph.

## Global cleanup budget

`limit` is a global logical budget. A graph counts as one logical cleanup unit even when it contains several Attempt rows. Therefore `CleanupResult.total_deleted <= limit`.

## Transaction semantics

Retention uses the same `UnitOfWork` boundary as scheduler writes. SQLite selects and deletes candidates while holding its `BEGIN IMMEDIATE` transaction; in-memory cleanup executes under the shared store lock.

## SQLite schema v8

LOT-32 introduces:

```text
SCHEMA_VERSION = 8
executions.completed_at
ix_executions_retention
ix_execution_requests_retention
ix_outbox_published
```

`completed_at` is an indexed persistence projection of the immutable terminal `ExecutionResult`. Existing v7 databases are upgraded by backfilling the value from `result_json` before creating the retention indexes.

## Observability

Each successful cleanup emits:

```text
retention.cleanup.completed
```

with aggregate counts for terminal graphs, orphan requests, published outbox messages, and total logical deletions.

## Safety invariants

1. Non-terminal Executions are never deleted.
2. Pending or admission-waiting Requests are never deleted.
3. Pending Outbox messages are never deleted.
4. Schedules are never deleted by retention.
5. Execution graphs are removed in referential order.
6. Cutoffs come from the explicit Scheduler Clock.
7. Cleanup is bounded by one global logical budget.
8. SQLite retention queries are indexed.
9. v7 terminal history is backfilled during migration to v8.
10. Cleanup is explicit rather than automatic.

## Qualification

LOT-32 qualifies terminal graph cleanup, active-state preservation, pending-outbox preservation, published-outbox cleanup, global budget behavior, SQLite referential deletion order, and schema v7→v8 migration/backfill.

## Production maturity roadmap

```text
LOT-30  Observability            ✅
LOT-31  Operational API          ✅
LOT-32  Retention / Cleanup      ✅
LOT-33  Additional Executors    ⏭ NEXT
LOT-34  Public API Hardening     ⬜
```

## Next

`LOT-33 — Additional Executors`
