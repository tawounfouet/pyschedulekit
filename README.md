# PyScheduleKit

> Learn scheduling by building a scheduling framework.

PyScheduleKit is a Python scheduling framework designed first as a rigorous learning project: model time, triggers, schedules, occurrences, execution requests, retries, persistence, recovery, and distributed coordination before hiding those concepts behind convenience APIs.

## Project status

**LOT-20 complete — next: LOT-21 SQL Persistence Foundations**

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
