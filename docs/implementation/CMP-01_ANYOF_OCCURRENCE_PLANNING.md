# CMP-01 — AnyOf Occurrence Planning

## Objective

Qualify the CMP-00 temporal union through the existing Schedule and Occurrence planning
pipeline without adding a composite-specific planner.

The architecture remains:

```text
AnyOfTrigger
     ↓
CalendarOccurrencePlanner
     ↓
Schedule checkpoint
     ↓
OccurrencePlanner
```

`AnyOfTrigger` already satisfies the structural `Trigger` protocol. Schedule creation,
checkpoint advancement and occurrence reconstruction therefore consume it through the same
boundary as Date, Interval and Cron triggers.

## Qualified behavior

CMP-01 proves that:

1. Schedule creation selects the earliest child candidate;
2. checkpoint advancement walks the ordered union of all children;
3. simultaneous child candidates produce one checkpoint and one Occurrence;
4. finite composition completes only when every child is exhausted;
5. pure occurrence projection never mutates Schedule state or persistence version;
6. backlog reconstruction is chronological, duplicate-free and bounded by its existing
   caller-supplied limit;
7. a Schedule-level BusinessCalendar filters composite candidates exactly like any other
   pure temporal Trigger.

## Calendar boundary

CMP-01 does not permit a `CalendarAwareTrigger` inside `AnyOfTrigger`. It only proves that
the existing Schedule-level calendar filter applies to the output stream of a pure temporal
composite.

This preserves one unambiguous rule:

```text
child temporal union
        ↓
Schedule-local calendar filter
        ↓
valid Occurrence
```

## Deliberate boundary

CMP-01 adds qualification, not a redundant planner abstraction. It still does not add:

- stable public imports;
- persisted codecs or migrations;
- InMemory / SQLite / PostgreSQL adapter parity;
- application-level catch-up/coalescing qualification;
- calendar-aware nested children;
- intersection semantics.

## Acceptance guarantees

- Schedule initialization and advancement consume the union correctly;
- shared Instants are materialized once;
- finite exhaustion transitions the Schedule to `COMPLETED`;
- OccurrencePlanner remains pure;
- due backlog ordering is deterministic;
- Schedule-level calendar filtering skips excluded composite candidates.

---

**Status:** CMP-01 — AnyOf Occurrence Planning implemented and locally qualified.
