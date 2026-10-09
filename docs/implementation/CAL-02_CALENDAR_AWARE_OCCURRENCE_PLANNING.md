# CAL-02 — Calendar-aware Occurrence Planning

## Objective

Turn an exact Schedule calendar binding into deterministic occurrence semantics without
moving business-calendar knowledge into Date, Interval or Cron triggers.

## Core rule

```text
Trigger
  ↓
candidate Instant
  ↓
CalendarOccurrencePlanner
  ↓
BusinessCalendar(snapshot exact)
  ↓
valid Occurrence
```

The Trigger remains responsible for temporal candidates. The calendar is responsible for
business-date validity. The planner coordinates them.

## Layering

```text
API Scheduler
   │
   ├── CalendarProvider (composition root)
   │
   ▼
application.resolve_calendar_binding()
   │
   ▼
immutable BusinessCalendar
   │
   ▼
domain CalendarOccurrencePlanner
```

The domain never calls a database, HTTP service, holiday package or provider.

## Deterministic resolution

A bound Schedule stores:

```text
CalendarSnapshotRef(CalendarRef, CalendarRevision)
```

The application must resolve that **exact revision**. Resolving "latest" during scheduling
would make historical decisions non-replayable and is therefore forbidden.

Missing or mismatched revisions fail closed.

## Candidate validation

For each Trigger candidate:

1. convert the Instant into the Schedule's configured timezone;
2. extract the local civil date;
3. apply the exact BusinessCalendar;
4. accept the candidate or continue to the next Trigger candidate.

This matters around midnight and timezone boundaries: business-date validity is not defined
from the UTC date.

## Operational checkpoint

`Schedule.next_run_time` is the next **valid** known occurrence, not merely the next raw
Trigger candidate.

Therefore an excluded weekend or holiday is skipped before it becomes durable due work.

## Recovery semantics

Catch-up and coalesce use the same planner as normal scheduling.

```text
raw Trigger candidates
        ↓
calendar filter
        ↓
valid historical occurrences
        ↓
misfire / catch-up / coalesce
```

A weekend that was never a valid occurrence cannot become catch-up work later.

## CAL-01 compatibility

CAL-01 persisted calendar bindings before calendar filtering affected checkpoints. A
Schedule may therefore be loaded with a due checkpoint that the bound calendar now rejects.

CAL-02 handles that state deterministically:

- no ExecutionRequest is created for the excluded checkpoint;
- the checkpoint advances to the next valid occurrence;
- the healed state is persisted through the existing optimistic-concurrency contract.

## Bounded planning

Calendar filtering may otherwise loop indefinitely with an impossible or pathological
calendar/trigger combination.

`CalendarOccurrencePlanner` therefore has a bounded candidate scan and raises
`CalendarPlanningLimitExceededError` after the configured limit.

## Compatibility

Unbound schedules retain the pre-CAL-02 behavior:

```text
Trigger.next_after(reference)
→ next_run_time
```

No calendar provider lookup occurs for them.

## Acceptance guarantees

1. weekends and holidays are skipped;
2. explicit extra working days are accepted;
3. validation uses the Schedule's local date;
4. the resolved calendar revision must exactly match the binding;
5. missing calendar configuration fails closed;
6. checkpoint advancement skips directly to the next valid occurrence;
7. catch-up never materializes excluded candidates;
8. legacy invalid checkpoints self-heal without an execution request;
9. candidate scanning is bounded;
10. unbound Schedule behavior remains compatible.

## Non-goals

CAL-02 does not implement intrinsic business-day trigger expressions such as:

- first working day of month;
- last business day;
- Nth working day;
- business-day offsets.

Those belong to **CAL-03 — Business-Day Trigger Semantics**.
