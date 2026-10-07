# PyScheduleKit

> Learn scheduling by building a scheduling framework.

PyScheduleKit is a Python scheduling framework designed first as a rigorous learning project: model time, triggers, schedules, occurrences, execution requests, retries, persistence, recovery, and distributed coordination before hiding those concepts behind convenience APIs.

## Project status

**LOT-28 complete — next: LOT-29 Distributed Scheduler Coordination**

Completed:

- LOT-00 — Repository & Packaging Foundation
- LOT-01 — Time Model
- LOT-02 — Trigger Foundations
- LOT-03 — DateTrigger & IntervalTrigger
- LOT-04 — CronTrigger
- LOT-05 — Schedule Aggregate
- LOT-06 — Occurrence Planning
- LOT-07 — In-Memory Persistence
- LOT-08 — SchedulerEngine
- LOT-09 — Execution Lifecycle
- LOT-10 — Local Executor
- LOT-11 — run_pending() End-to-End Slice
- LOT-12 — Misfire Policy Foundations
- LOT-13 — Catch-Up & Coalescing
- LOT-14 — Concurrency Policy Foundations
- LOT-15 — Retry Policy Foundations
- LOT-16 — Execution Timeout
- LOT-17 — Cancellation Refinements
- LOT-18 — Continuous Scheduler Loop
- LOT-19 — Wake-up Strategy
- LOT-20 — Graceful Shutdown
- LOT-21 — SQL Persistence Foundations
- LOT-22 — Transactions / DB Constraints
- LOT-23 — Crash Recovery
- LOT-24 — Reconciliation
- LOT-25 — Transactional Outbox
- LOT-26 — Distributed Claims
- LOT-27 — Multi-worker Admission
- LOT-28 — Lease / Fencing Refinements

The implementation follows a domain-first roadmap:

```text
Time → Trigger → Schedule → Occurrence → SchedulerEngine
     → Execution → Runtime → Persistence → Recovery → Distribution
```

The first executable milestone remains intentionally small:

```text
MutableClock
    ↓
IntervalTrigger(10m)
    ↓
Schedule
    ↓
run_pending()
    ↓
exactly one successful local Execution
```

## Architectural principles

- Domain logic stays independent from infrastructure.
- Time is explicit and testable; no hidden wall-clock access in the domain.
- Triggers calculate temporal occurrences; they do not execute work.
- Schedule and Execution have distinct lifecycles.
- Repositories never commit implicitly.
- External side effects never precede durable intent once persistence is enabled.
- Configuration is declarative data, not executable code.
- Every supported guarantee must map to an executable test.

## Current temporal foundation

LOT-01 introduces:

```python
from pyschedulekit.domain.time import Duration, Instant, Timezone
from pyschedulekit.testing import FixedClock, MutableClock
```

Key semantics:

- `Instant` values are timezone-aware and normalized to UTC.
- `Duration` represents elapsed time; one day is exactly 24 hours.
- `Timezone` uses IANA timezone data and rejects unresolved DST gaps.
- ambiguous DST local times require an explicit `fold`.
- `TimeWindow` uses `[start, end)` boundaries.
- the scheduling domain never reads the host clock directly.

## Current trigger foundation

LOT-02 introduces the structural contract:

```python
from pyschedulekit.domain.trigger import Trigger


class Trigger(Protocol):
    def next_after(self, reference: Instant) -> Instant | None: ...
```

Every future built-in Trigger must preserve deterministic results and strict temporal progression. The reusable `TriggerContractSuite` makes those invariants executable.

## First concrete triggers

LOT-03 adds the first real temporal rules:

```python
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import DateTrigger, IntervalTrigger
```

`DateTrigger` emits one finite absolute occurrence. `IntervalTrigger` is fixed-rate and remains anchored:

```text
anchor
anchor + interval
anchor + 2 × interval
...
```

Late execution never shifts the recurrence, and far-future lookup uses direct arithmetic rather than replaying historical occurrences.

LOT-04 adds `CronTrigger` as an explicit calendar rule with five numeric fields, IANA timezone semantics, Vixie day matching, bounded lookup, and explicit DST gap/fold policies.

## Cron trigger

LOT-04 completes the V1 trigger family:

```python
CronTrigger(
    "0 9 * * 1-5",
    timezone=Timezone("Europe/Paris"),
)
```

Cron evaluates civil calendar time rather than elapsed duration. DST gaps are skipped by default, ambiguous local times select the first fold by default, and both behaviors can be made strict/explicit.

## Schedule aggregate

LOT-05 introduces the first Aggregate Root:

```text
Schedule
├── ScheduleId
├── ScheduleDefinition
├── ScheduleState
├── ScheduleRevision
├── PersistenceVersion
└── next_run_time
```

The lifecycle is explicit:

```text
ACTIVE
├── pause()  → PAUSED
├── cancel() → CANCELLED
└── exhausted Trigger → COMPLETED
```

`ScheduleRevision` changes only when the functional definition changes; `PersistenceVersion` changes for durable operational mutations as well.

## Occurrence planning

LOT-06 introduces immutable logical occurrences:

```text
OccurrenceKey
=
ScheduleId
+
ScheduleRevision
+
ScheduledAt
```

`OccurrencePlanner` can project the current Schedule checkpoint or calculate a future occurrence without mutating the Schedule. This deterministic identity will later back durable uniqueness and distributed deduplication.

## Transactional in-memory persistence

LOT-07 introduces the first persistence ports and adapter:

```text
UnitOfWork
   │
   ▼
ScheduleRepository
   │
   ▼
InMemoryScheduleStore
```

Repositories never commit implicitly. Each UnitOfWork owns an identity map and write set, while commit validates the loaded `PersistenceVersion` against committed state before applying any write.

The adapter also exposes deterministic due-Schedule selection ordered by `next_run_time` and `ScheduleId`.

## SchedulerEngine

LOT-08 introduces the first scheduling application service:

```text
evaluation_now
   ↓
list_due()
   ↓
reload Schedule
   ↓
Occurrence
   ↓
ExecutionRequest
   +
advance next_run_time
   ↓
atomic commit
```

The engine never invokes workload code. It materializes one due occurrence per Schedule per cycle and persists the request together with checkpoint advancement.

## Execution lifecycle

LOT-09 separates durable intent from logical execution and concrete attempts:

```text
ExecutionRequest
      ↓
Execution
      ↓
Attempt #1
      ↓
AttemptResult
      ↓
ExecutionResult
```

A retry keeps the same `ExecutionId` and `IdempotencyKey` while creating a new numbered Attempt.

## Local executor

LOT-10 executes the first real Python workload through an explicit registry:

```text
TargetRef.python("refresh")
        ↓
PythonTargetRegistry
        ↓
Attempt RUNNING committed
        ↓
callable invoked outside transaction
        ↓
SUCCESS or normalized Failure
```

Persisted target data never authorizes arbitrary Python imports.

## End-to-end run_pending()

LOT-11 connects the complete in-memory local slice:

```text
Scheduler.run_pending()
        ↓
SchedulerEngine
        ↓
ExecutionRequest
        ↓
Execution
        ↓
Attempt
        ↓
LocalExecutor
        ↓
Python callable
```

The cycle is one-shot and non-blocking. It also resumes durable PENDING requests and QUEUED executions left by earlier cycles.

## Misfire policy foundations

LOT-12 makes lateness explicit:

```text
scheduled_at
    +
GracePeriod
    +
evaluation_now
    ↓
ON_TIME / LATE_ELIGIBLE / MISFIRED
    ↓
MisfirePolicy
```

`SKIP`, `RUN_NOW`, `CATCH_UP`, and `COALESCE` are now executable end-to-end. Catch-Up drains bounded oldest-first batches; Coalesce requires a complete bounded scan and fails closed when the true latest due occurrence cannot be proven.

## Catch-Up and Coalescing

LOT-13 adds bounded backlog recovery:

```text
CATCH_UP
→ materialize up to max_occurrences oldest-first
→ continue next cycle when has_more

COALESCE
→ scan up to max_occurrences
→ materialize only the true latest due occurrence
→ no mutation when the scan bound is insufficient
```

Existing durable ExecutionRequests are always preserved.

## Concurrency policy foundations

LOT-14 adds explicit admission control after durable request materialization:

```text
ExecutionRequest
    ↓
ConcurrencyEvaluator
    ↓
ADMIT / QUEUE / DROP
    ↓
ConcurrencyCoordinator
```

`ConcurrencyPolicy.allow()` preserves the historical behavior. `ConcurrencyPolicy.limit(max_instances=N)` can queue overflow in `WAITING_ADMISSION` or terminate it as `DROPPED`. The V1 coordinator serializes admission across all coordinators in one Python process; distributed enforcement is intentionally deferred.

## Retry policy foundations

LOT-15 turns the RETRY_WAIT state introduced by the execution lifecycle into an operational policy:

```text
Attempt failure
    ↓
RetryEvaluator
    ├── STOP  → terminal failure
    └── RETRY → RETRY_WAIT
                   ↓
             next_attempt_at
                   ↓
             run_pending()
```

Retries preserve one logical Execution and create numbered Attempts. Backoff is represented as a future deadline rather than `sleep()`, so the one-shot runtime remains non-blocking.

Public configuration:

```python
RetryPolicy(
    max_attempts=3,
    backoff=FixedBackoff(Duration.seconds(5)),
)
```

`max_attempts` includes the initial Attempt. The neutral default is one total attempt.

## Execution timeout

LOT-16 makes timeout operational at Attempt level. A configured deadline produces `TIMED_OUT`; RetryPolicy may then move the Execution to `RETRY_WAIT` or let it terminate as `TIMED_OUT`.

```python
scheduler.add_schedule(
    target=my_job,
    trigger=my_trigger,
    timeout=Duration.seconds(30),
)
```

The local runtime regains control when the deadline expires. Because Python cannot safely kill an arbitrary thread, an expired callable may still finish in its daemon worker; LOT-17 will refine cancellation/cooperative termination semantics.

## Cancellation refinements

LOT-17 adds explicit execution cancellation:

```python
scheduler.cancel_execution(execution_id)
```

Token-aware local workloads can cooperate:

```python
def job(cancellation_token: CancellationToken) -> None:
    while work_remains():
        cancellation_token.raise_if_cancelled()
        do_one_unit()
```

QUEUED and RETRY_WAIT work cancels immediately. RUNNING work records durable cancellation intent and receives a process-local signal. CANCELLED is terminal and never retried.

## Continuous scheduler loop

LOT-18 layers a blocking runtime over the existing one-shot primitive:

```python
scheduler.run_forever(
    poll_interval=Duration.seconds(1),
)
```

The runtime repeatedly calls `run_pending()` at a fixed cadence. `scheduler.stop()` interrupts the current wait immediately. Runtime state is observable through `is_running`, `cycles_completed`, and `last_result`.

LOT-19 will replace fixed polling with a smarter wake-up strategy without changing the scheduling semantics inside `run_pending()`.

## Wake-up strategy

LOT-19 replaces fixed polling as the primary wait decision with durable-state-driven planning:

```text
run_pending()
    ↓
earliest of:
- due/pending work
- retry next_attempt_at
- schedule next_run_time
    ↓
bounded by max_sleep
```

Runtime mutations such as `add_schedule()` and `cancel_execution()` interrupt the current wait so the plan is recomputed immediately.

```python
scheduler.run_forever(
    max_sleep=Duration.seconds(30),
)
```

The older `poll_interval=` argument remains accepted as a compatibility alias for `max_sleep`.

## Graceful shutdown

LOT-20 separates loop stopping from runtime draining:

```python
scheduler.shutdown(
    mode=ShutdownMode.WAIT,
    timeout=Duration.seconds(30),
)
```

or cooperative cancellation:

```python
scheduler.shutdown(
    mode=ShutdownMode.CANCEL,
    timeout=Duration.seconds(30),
)
```

The shutdown gate prevents new Attempts from starting once drain begins. WAIT lets active work finish; CANCEL signals LOT-17 cancellation tokens. A timeout returns a structured result containing any Execution IDs still active.

## SQL persistence foundations

LOT-21 adds a durable SQLite adapter without changing the domain or application layer:

```python
from pyschedulekit import Scheduler, SqliteUnitOfWorkFactory

scheduler = Scheduler(
    uow_factory=SqliteUnitOfWorkFactory("scheduler.db"),
)
```

Runtime query fields remain relational SQL columns, while immutable definitions and policies use versioned JSON snapshots. The adapter preserves the existing identity-map, write-set, commit/rollback, and optimistic-version semantics.

LOT-22 will harden database constraints and transaction guarantees.

## Transaction and database constraints

LOT-22 hardens SQLite as an integrity boundary:

```text
Domain invariants
        +
UnitOfWork semantics
        +
SQLite FK / UNIQUE / CHECK
        +
versioned compare-and-swap UPDATE
```

Schema v1 databases from LOT-21 migrate automatically to schema v2. Foreign keys are enabled on every connection, natural execution identities are unique in the database, and stale updates include the expected version in the SQL WHERE predicate.

## Crash recovery

LOT-23 reconciles persisted RUNNING work before a restarted Scheduler begins new scheduling activity.

```text
RUNNING Execution + RUNNING Attempt
        ↓ process crash
restart
        ↓
Attempt FAILED with execution.crash_recovered
        ↓
RetryPolicy
        ↓
RETRY_WAIT or terminal FAILED
```

A previously persisted cancellation request wins over retry and recovers to CANCELLED instead.

Recovery runs automatically before the first `run_pending()` or `run_forever()` cycle and is inspectable through `last_recovery_result`. If persisted RUNNING state cannot be reconciled safely, scheduling fails closed with `CrashRecoveryIncompleteError`.

## Reconciliation

LOT-24 validates the durable execution graph after crash recovery and before new scheduling work.

```text
Crash Recovery
      ↓
Reconciliation
      ↓
Scheduling
```

Safe deterministic drift is repaired automatically: a DISPATCHED request missing its Execution is reconstructed, and a request with an already-existing Execution is restored to DISPATCHED. Ambiguous historical drift is reported instead of guessed.

Reconciliation uses bounded scans and fails closed if the graph cannot be proven complete and coherent.

## Transactional outbox

LOT-25 closes the durable dual-write gap between scheduler state and integration intent:

```text
business lifecycle mutation
        +
OutboxMessage PENDING
        ↓
same UnitOfWork / same SQL transaction
        ↓
external publication later
```

Publication is explicitly at-least-once. `OutboxMessage.id` is the consumer idempotency key, and consumers are expected to deduplicate replays with it.

```python
result = scheduler.dispatch_outbox(publisher)
```

The external publisher runs outside the scheduler lifecycle transaction; failed publication leaves the message PENDING for a later retry.

With LOT-25, the Durability phase is complete. LOT-26 starts distributed ownership with claims.

## Distributed execution claims

LOT-26 starts the Distribution phase by closing the race between multiple workers observing the same runnable Execution.

```text
QUEUED / due RETRY_WAIT
        ↓
durable claim
        ↓
claim ownership validation
        ↓
atomic claim consumption + Attempt start
        ↓
RUNNING
```

```python
scheduler = Scheduler(
    uow_factory=SqliteUnitOfWorkFactory("scheduler.db"),
    worker_id="worker-a",
    claim_ttl=Duration.seconds(30),
)
```

Claims are one-shot admission tokens, not yet renewable execution leases. Expired claims can be taken over, and stale claim handles are rejected at Attempt start.

## Multi-worker admission

LOT-27 makes `ConcurrencyPolicy.limit(max_instances=N)` global across cooperating workers sharing the same durable store.

```text
ScheduleAdmissionLock
        ↓
count non-terminal Executions
        ↓
ADMIT / QUEUE / DROP
        ↓
commit
        ↓
release
```

Admission-lock contention is reported separately from a real policy QUEUE. SQLite schema v5 persists the short-lived Schedule-scoped locks.

## Lease and fencing refinements

LOT-28 extends Execution claims across the full RUNNING Attempt:

```text
claim generation N
        ↓
Attempt RUNNING
        ↓
heartbeat renewals
        ↓
fenced completion
        ↓
claim RELEASED
```

Takeover increments the generation. A stale worker cannot finalize scheduler state after a newer owner or recovery pass has taken control.

Trusted local callables may explicitly request `fencing_token`, which is the current Execution lease generation.

Crash recovery now preserves RUNNING work protected by an active lease instead of treating every RUNNING row as orphaned. Admission decisions are also fenced by committing lock release and ADMIT/QUEUE/DROP in one UnitOfWork.

## Package shape

```text
src/pyschedulekit/
├── domain/
├── application/
├── ports/
├── infrastructure/
└── testing/
```

The directory structure grows only when implementation needs it; the project avoids empty architectural ceremony before working vertical slices.

## Development

Target baseline: **Python 3.11+**.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e ".[dev]"
pytest
ruff check .
mypy src
```

## Roadmap

Initial implementation path:

1. Repository & packaging foundation
2. Time model
3. Trigger foundations
4. Date/Interval triggers
5. Schedule aggregate
6. Occurrence planning
7. In-memory persistence
8. Scheduler engine
9. Execution lifecycle
10. Local executor
11. `run_pending()`

Cron, continuous runtime, policies, durable persistence, outbox, crash recovery, and distributed coordination are layered on only after the in-memory scheduling semantics are proven.

## License

MIT
