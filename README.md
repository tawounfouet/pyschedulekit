# PyScheduleKit

> Learn scheduling by building a scheduling framework.

PyScheduleKit is a Python scheduling framework designed first as a rigorous learning project: model time, triggers, schedules, occurrences, execution requests, retries, persistence, recovery, and distributed coordination before hiding those concepts behind convenience APIs.

## Project status

**Implementation — LOT-04: CronTrigger**

Completed:

- LOT-00 — Repository & Packaging Foundation
- LOT-01 — Time Model
- LOT-02 — Trigger Foundations
- LOT-03 — DateTrigger & IntervalTrigger
- LOT-04 — CronTrigger (branch qualification in progress)
- LOT-05 — Schedule Aggregate
- LOT-06 — Occurrence Planning
- LOT-07 — In-Memory Persistence
- LOT-08 — SchedulerEngine
- LOT-09 — Execution Lifecycle
- LOT-10 — Local Executor
- LOT-11 — run_pending() End-to-End Slice

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
