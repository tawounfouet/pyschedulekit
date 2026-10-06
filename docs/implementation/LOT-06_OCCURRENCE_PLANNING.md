# LOT-06 — Occurrence Planning

## Goal

Introduce the immutable temporal fact that links a Schedule revision to one scheduled Instant.

The central object is:

```text
Occurrence
├── ScheduleId
├── ScheduleRevision
└── ScheduledAt
```

## Occurrence versus Schedule

A Schedule is a durable planning aggregate.

An Occurrence is one logical temporal fact derived from that planning definition.

```text
Schedule
   │
   │ Trigger / next_run_time
   ▼
Occurrence
```

The Occurrence does not execute work.

It does not contain Attempt state, retry state, executor state or runtime ownership.

Those belong to later objects.

## OccurrenceKey

The natural identity is:

```text
OccurrenceKey
=
ScheduleId
+
ScheduleRevision
+
ScheduledAt
```

This is deliberately not a random UUID.

Two independent scheduler nodes that calculate the same logical occurrence must be able to derive the same identity components.

## Why ScheduleRevision is part of the key

Consider:

```text
Schedule A
Revision 1
scheduled_at = 10:00
```

Then the Schedule is rescheduled and becomes:

```text
Schedule A
Revision 2
scheduled_at = 10:00
```

These are not automatically the same logical scheduling fact.

Including the revision preserves the definition lineage:

```text
(A, revision 1, 10:00)
≠
(A, revision 2, 10:00)
```

## Why PersistenceVersion is not part of the key

PersistenceVersion tracks durable record mutation and optimistic concurrency.

Operations such as:

- checkpoint advancement;
- pause;
- resume;

may change PersistenceVersion without changing the functional scheduling definition.

Therefore:

```text
Occurrence identity
uses ScheduleRevision

not PersistenceVersion
```

## Occurrence is immutable

`Occurrence` and `OccurrenceKey` are frozen Value Objects.

Once created:

```text
scheduled_at
schedule_id
schedule_revision
```

do not change.

If the planning definition changes, a different Occurrence is produced rather than mutating an existing one.

## OccurrencePlanner

LOT-06 introduces a pure domain service:

```python
planner = OccurrencePlanner()
```

It supports two distinct projections.

### current(schedule)

```python
planner.current(schedule)
```

returns the Occurrence represented by the Schedule's current `next_run_time`.

For non-active Schedules:

```text
PAUSED
CANCELLED
COMPLETED
```

the result is:

```text
None
```

because those states expose no current schedulable checkpoint.

### next_after(schedule, reference)

```python
planner.next_after(schedule, reference)
```

asks the Schedule Trigger for the next candidate after the supplied Instant and wraps it as an Occurrence.

Important:

> This method does not advance Schedule.next_run_time.

It is a pure projection.

This distinction will become useful for:

- catch-up reconstruction;
- simulation;
- diagnostics;
- future occurrence inspection.

## Mutation boundary

LOT-06 intentionally separates:

```text
OccurrencePlanner
→ calculates
```

from:

```text
Schedule.advance_next_run_after()
→ mutates operational checkpoint
```

The future SchedulerEngine will coordinate both operations in the correct transactional order.

## Why TargetRef is not copied into Occurrence

An Occurrence represents:

> This Schedule revision planned something at this Instant.

It does not yet represent an execution command.

The future `ExecutionRequest` will be responsible for capturing:

- TargetRef;
- execution policy snapshots;
- idempotency information;
- correlation context.

Keeping those concerns out of Occurrence prevents the temporal identity object from becoming a premature execution envelope.

## Qualification mapping

LOT-06 implements:

- `T-SCH-020` — OccurrenceKey deterministic;
- `T-SCH-021` — different ScheduleRevision produces different key;
- `T-SCH-022` — Occurrence scheduled_at immutable.

Additional tests prove:

- Occurrence.key reflects the three identity components;
- current active Schedule projects its checkpoint;
- future planning is pure and does not mutate next_run_time;
- future planning does not increment PersistenceVersion;
- paused/cancelled/completed Schedules expose no current occurrence;
- rescheduling preserves ScheduleId but changes occurrence revision identity;
- reconstructing the same three components recreates the same logical identity.

## Future persistence consequence

The eventual persistence model can enforce uniqueness using the equivalent of:

```text
UNIQUE (
    schedule_id,
    schedule_revision,
    scheduled_at
)
```

This will become one of the fundamental duplicate-prevention mechanisms.

## Important guarantee

The presence of a deterministic OccurrenceKey does not mean:

```text
exactly-once side effects
```

It means:

```text
same logical occurrence
can be recognized as the same logical occurrence
```

Delivery and execution semantics remain separate concerns.

## Intentionally deferred

LOT-06 does not implement:

- persisted Occurrence rows;
- ExecutionRequest;
- unique database constraints;
- calendars;
- ScheduleWindow filtering;
- misfire;
- catch-up policy;
- coalescing;
- SchedulerEngine mutation orchestration.

## Architecture progression

```text
Trigger
   │
   ▼
Schedule
   │
   ▼
OccurrencePlanner
   │
   ▼
Occurrence
   │
   ▼
OccurrenceKey

NEXT:
Repository / UnitOfWork boundary
```

## Exit criteria

LOT-06 is complete when:

- Occurrence identity is deterministic;
- ScheduleRevision is part of logical identity;
- PersistenceVersion is not;
- Occurrence is immutable;
- planning does not mutate Schedule state;
- non-active Schedules do not project schedulable occurrences;
- relevant T-SCH occurrence tests are green.

## Next

`LOT-07 — In-Memory Persistence`
