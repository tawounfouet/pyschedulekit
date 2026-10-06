# LOT-05 — Schedule Aggregate

## Goal

Introduce the first durable domain Aggregate Root in PyScheduleKit.

A Schedule represents a temporal planning definition and its lifecycle. It does not execute work and it does not own execution attempts.

## Domain objects

This lot adds:

- `ScheduleId`
- `ScheduleRevision`
- `PersistenceVersion`
- `ScheduleState`
- `TargetRef`
- `ScheduleDefinition`
- `Schedule`

## Aggregate boundary

```text
Schedule
├── identity
├── immutable definition
├── lifecycle state
├── definition revision
├── persistence version
└── next_run_time operational checkpoint
```

The aggregate controls its own state transitions. Callers do not mutate lifecycle fields directly.

## ScheduleState

V1 states:

```text
ACTIVE
PAUSED
CANCELLED
COMPLETED
```

### ACTIVE

An active Schedule must expose a `next_run_time`.

### PAUSED

A paused Schedule does not expose a `next_run_time` and therefore cannot be selected as due work.

### CANCELLED

Terminal state. No future scheduling is allowed.

### COMPLETED

Terminal state reached when a finite Trigger is exhausted.

## ScheduleRevision versus PersistenceVersion

These counters have different semantics.

### ScheduleRevision

`ScheduleRevision` changes only when the functional definition changes.

Examples:

- replacing the Trigger;
- changing the TargetRef;
- changing the effective timezone.

```text
definition v1
→ reschedule
definition v2
```

### PersistenceVersion

`PersistenceVersion` models durable record mutation / optimistic concurrency.

It changes when durable Schedule state changes, including:

- pause;
- resume;
- cancel;
- reschedule;
- operational next-run advancement.

Therefore:

```text
ScheduleRevision
≠
PersistenceVersion
```

This distinction is intentional from the first aggregate implementation.

## TargetRef

`TargetRef` is declarative.

Example:

```python
TargetRef.python("app.tasks:refresh")
```

The Schedule does not resolve or execute the target.

Resolution remains a later Executor concern.

Current convenience constructors:

- `TargetRef.python(...)`
- `TargetRef.workflow(...)`
- `TargetRef.http(...)`

These constructors create references only. They do not imply that matching executors are already implemented.

## ScheduleDefinition

The current immutable definition contains:

```text
TargetRef
Trigger
Timezone
```

The default effective timezone is UTC.

Policy sets, calendars, windows, metadata, retry and concurrency options remain deferred until their dedicated lots.

## Creation

Creation requires an explicit temporal reference:

```python
Schedule.create(
    schedule_id=...,
    definition=...,
    reference=...,
)
```

The aggregate asks its Trigger for:

```text
next_after(reference)
```

If a future candidate exists:

```text
state = ACTIVE
next_run_time = candidate
```

If the Trigger is already exhausted:

```text
state = COMPLETED
next_run_time = None
```

No Clock is read by the aggregate.

## Pause semantics

```text
ACTIVE
  │ pause()
  ▼
PAUSED
```

Pause is idempotent.

Pausing clears `next_run_time`.

This prevents paused Schedules from appearing in due-work queries.

## Resume semantics

Resume requires:

```python
resume(reference=now)
```

The next occurrence is recalculated from that explicit reference.

V1 rule:

> Time spent paused does not automatically become catch-up backlog.

Example:

```text
interval = 10m
pause at 10:05
resume at 10:25

next_run_time = 10:30
```

not:

```text
10:10
10:20
```

Catch-up behavior is a separate policy problem.

## Cancel semantics

```text
ACTIVE / PAUSED
      │
      ▼
  CANCELLED
```

Cancel is idempotent once already cancelled.

Cancellation only stops future scheduling.

It does not imply cancellation of already-created Executions. That guarantee will be exercised once the Execution aggregate exists.

## Completion

When:

```text
Trigger.next_after(reference) == None
```

the Schedule becomes:

```text
COMPLETED
```

This is especially important for finite triggers such as `DateTrigger`.

## Reschedule

`reschedule()`:

- preserves `ScheduleId`;
- replaces `ScheduleDefinition`;
- increments `ScheduleRevision` exactly once;
- increments `PersistenceVersion`;
- recalculates `next_run_time` if currently ACTIVE;
- remains PAUSED when rescheduling a paused Schedule;
- rejects terminal Schedules.

Example:

```text
ScheduleId = A
Revision = 1
Interval = 10m

reschedule → 30m

ScheduleId = A
Revision = 2
Interval = 30m
```

## Operational checkpoint advancement

`advance_next_run_after(reference=...)` is intentionally distinct from rescheduling.

It advances:

```text
next_run_time
PersistenceVersion
```

but leaves:

```text
ScheduleRevision
```

unchanged.

This encodes the distinction between:

> The business definition changed

and:

> The scheduler processed another temporal checkpoint.

## Anti-regression invariant

The aggregate rejects checkpoint advancement from a reference before the currently scheduled checkpoint.

This prevents accidental operational rewind.

## Core invariants

The current aggregate enforces:

```text
ACTIVE
→ next_run_time is not None

PAUSED / CANCELLED / COMPLETED
→ next_run_time is None
```

and:

```text
terminal Schedule
→ cannot resume
→ cannot reschedule
```

## Qualification mapping

Implemented in this lot:

- `T-SCH-001` — create valid Schedule;
- `T-SCH-002` — pause active Schedule;
- `T-SCH-003` — pause idempotence;
- `T-SCH-004` — resume paused Schedule;
- `T-SCH-005` — resume cancelled Schedule rejected;
- `T-SCH-006` — cancel active Schedule;
- `T-SCH-007` — cancel idempotence;
- `T-SCH-008` — Trigger exhaustion completes Schedule;
- `T-SCH-009` — reschedule increments revision;
- `T-SCH-010` — checkpoint update does not increment ScheduleRevision;
- `T-SCH-011` — reschedule preserves ScheduleId;
- `T-SCH-015` — effective timezone remains part of the frozen definition.

Additional tests cover:

- immediately exhausted Schedule creation;
- paused reschedule semantics;
- terminal reschedule rejection;
- operational rewind rejection;
- immutable ScheduleDefinition;
- immutable TargetRef;
- revision/version distinction.

## Deferred acceptance scenarios

The following scenarios depend on the future Execution aggregate and are therefore not faked in LOT-05:

- `T-SCH-012` — existing Execution unaffected by reschedule;
- `T-SCH-013` — pause does not cancel active Execution;
- `T-SCH-014` — cancel Schedule does not cancel active Execution.

They will be activated when Execution exists.

## Intentionally deferred

LOT-05 does not yet implement:

- Occurrence;
- ExecutionRequest;
- Execution;
- policies;
- persistence repositories;
- Schedule serialization;
- public ScheduleHandle;
- ScheduleService;
- direct callable Targets.

## Architecture progression

```text
Trigger
   │
   ▼
ScheduleDefinition
   │
   ▼
Schedule Aggregate
   │
   ▼
next_run_time

NEXT:
Occurrence
```

## Exit criteria

LOT-05 is complete when:

- lifecycle transitions are controlled by the Aggregate Root;
- functional and persistence versions are distinct;
- ScheduleId survives rescheduling;
- paused/cancelled/completed Schedules expose no due checkpoint;
- Trigger exhaustion closes the Schedule;
- no hidden Clock is introduced;
- terminal states cannot be reopened;
- the applicable `T-SCH-*` suite is green.

## Next

`LOT-06 — Occurrence Planning`
