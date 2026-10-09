# CAL-01 — Schedule Calendar Binding

## Objective

Bind a Schedule to one exact, deterministic calendar revision without yet changing
occurrence-generation semantics.

CAL-00 established versioned calendar objects. CAL-01 makes the reference part of the
Schedule functional definition so later calendar-aware planning can operate on an explicit,
replayable input.

## Scope

CAL-01 adds:

- `ScheduleDefinition.calendar: CalendarSnapshotRef | None`;
- public `Scheduler.add_schedule(calendar=...)`;
- `ScheduleSnapshot.calendar` for operational inspection;
- SQL definition JSON encoding/decoding for the optional snapshot reference;
- backward-compatible decoding of historical definition JSON without a `calendar` key;
- adapter parity proving the binding survives InMemory, SQLite and PostgreSQL round-trips;
- domain qualification proving a calendar change through `reschedule()` advances
  `ScheduleRevision`.

## Determinism rule

```text
Schedule
   │
   └── CalendarSnapshotRef
          ├── CalendarRef
          └── CalendarRevision
```

A Schedule never stores a mutable provider object or an implicit "latest calendar" lookup.
It records the exact revision selected by the caller.

## Persistence

No new SQL column is required in CAL-01. The existing `schedules.definition_json` payload
stores the optional binding.

The Schedule-definition codec advances from v1 to **v2** because the calendar reference is
functional state. Current code reads legacy v1 definitions and writes v2 only. Future
unsupported versions fail closed, preventing an older runtime from silently reading and
rewriting a calendar-bound definition while dropping the binding.

Legacy v1 payloads without the key decode to `calendar=None`.

## Explicit non-goal

CAL-01 does not resolve or evaluate the calendar while calculating `next_run_time`.
Date, Interval and Cron behavior therefore remains unchanged whether a Schedule is bound or
not.

Calendar-aware occurrence filtering starts in CAL-02.

## Acceptance guarantees

1. A Schedule may be created with or without a calendar binding.
2. The exact `CalendarSnapshotRef` is visible through `ScheduleSnapshot`.
3. Bound schedules round-trip without information loss on every qualified persistence
   adapter.
4. Historical persisted v1 schedules without a calendar remain readable.
5. Schedule definitions are written as codec v2 and unsupported future versions fail closed.
6. Rebinding through `Schedule.reschedule()` increments `ScheduleRevision`.
7. CAL-01 does not alter occurrence timestamps.

## Next

**CAL-02 — Calendar-aware Occurrence Planning** will consume the exact bound snapshot through
the provider boundary and define how trigger candidates interact with working/non-working
calendar days.
