# 0.3.x — Calendar Foundations

CAL-00 introduced the temporal calendar abstractions that were specified from the beginning
but intentionally deferred until the core scheduler, persistence and execution ecosystem
were mature.

CAL-01 binds a Schedule definition to an exact optional `CalendarSnapshotRef`. CAL-02
consumes that binding during occurrence planning, and CAL-03 adds the first intrinsic
calendar-aware trigger for monthly business-day rules.

## Why calendars are separate from Cron

Cron can express rules such as:

```text
09:00 Monday-Friday
```

It cannot by itself define the business meaning of:

```text
first working day of the month
market holiday
company closure
exceptional working Saturday
regional business week
```

Those facts belong to an explicit business calendar.

## Domain model

### CalendarRef

`CalendarRef` is the stable logical identity of a shared calendar:

```python
CalendarRef("fr-business-days")
```

It contains no database/API/library knowledge.

### CalendarRevision

Calendars can evolve. `CalendarRevision` gives each immutable definition a positive,
monotonic revision number.

```text
fr-business-days / revision 1
fr-business-days / revision 2
fr-business-days / revision 3
```

### CalendarSnapshotRef

Historical scheduling decisions need a deterministic reference:

```python
CalendarSnapshotRef(
    calendar_ref=CalendarRef("fr-business-days"),
    revision=CalendarRevision(3),
)
```

This prevents a later change to a holiday calendar from silently changing the interpretation
of an old decision.

### BusinessCalendar

`BusinessCalendar` is an immutable set of working-day rules:

- configurable working weekdays;
- explicit holidays;
- explicit extra working days;
- exact `CalendarRef` + `CalendarRevision`.

Weekday numbers follow Python's `date.weekday()` convention:

```text
Monday = 0
...
Sunday = 6
```

There is deliberately **no universal Monday-Friday assumption** beyond the default
constructor value.

Explicit holidays and extra working days must be disjoint. CAL-00 rejects ambiguity instead
of inventing a hidden precedence rule.

## Provider port

`CalendarProvider` is the domain-facing port:

```python
calendar = provider.resolve(
    CalendarRef("fr-business-days"),
    revision=CalendarRevision(3),
)
```

Omitting `revision` resolves the latest registered revision.

The domain therefore does not depend on:

- a holiday Python package;
- a database;
- an HTTP API;
- a regulatory-calendar SaaS.

## In-memory adapter

`InMemoryCalendarProvider` is the first concrete adapter.

It is:

- process-local;
- thread-safe;
- explicitly populated;
- revision-aware;
- deterministic.

Unknown static calendars use the existing `PyScheduleKitConfigurationError` family, in line
with the V1 error-model specification.

## Example

```python
from datetime import date

from pyschedulekit import (
    BusinessCalendar,
    CalendarRef,
    CalendarRevision,
    InMemoryCalendarProvider,
)

calendar = BusinessCalendar(
    calendar_ref=CalendarRef("fr-business-days"),
    revision=CalendarRevision(1),
    holidays=frozenset({date(2026, 7, 14)}),
    extra_working_days=frozenset({date(2026, 1, 10)}),
)

provider = InMemoryCalendarProvider([calendar])

resolved = provider.resolve(CalendarRef("fr-business-days"))

assert not resolved.is_working_day(date(2026, 7, 14))
assert resolved.is_working_day(date(2026, 1, 10))
```

## Determinism contract

```text
logical CalendarRef
       +
exact CalendarRevision
       ↓
CalendarSnapshotRef
       ↓
immutable BusinessCalendar
       ↓
replayable calendar decision
```

CAL-00 establishes this contract before any Schedule persists a calendar reference.

## CAL-01 — Schedule Calendar Binding

A Schedule may now carry one exact calendar snapshot through
`Scheduler.add_schedule(calendar=...)`.

The binding is part of the immutable `ScheduleDefinition`, is exposed by
`ScheduleSnapshot.calendar`, and round-trips through InMemory, SQLite and PostgreSQL
persistence. Historical definition JSON without a `calendar` key remains readable and
decodes to `None`.

Changing the bound snapshot through `Schedule.reschedule()` is a functional-definition
change and therefore advances `ScheduleRevision`.

### CAL-01 boundary

CAL-01 deliberately stopped at the durable binding. CAL-02 now consumes that binding during
occurrence planning.

## CAL-02 — Calendar-aware Occurrence Planning

The planning pipeline is now explicit:

```text
Trigger
  ↓
candidate Instant
  ↓
Schedule timezone → local date
  ↓
exact BusinessCalendar revision
  ↓
valid Occurrence
  ↓
Schedule.next_run_time
```

`DateTrigger`, `IntervalTrigger` and `CronTrigger` remain pure temporal candidate
producers. They do not embed country holidays or company rules.

A calendar-bound Schedule resolves the exact `CalendarSnapshotRef` through the configured
`CalendarProvider` at the application boundary. The domain receives only the immutable
resolved `BusinessCalendar`.

The planner:

- filters candidates by the Schedule's **local date**, not by UTC date;
- honors working weekdays, holidays and explicit extra working days;
- jumps `next_run_time` directly over excluded dates;
- applies the same filter to catch-up/coalesce reconstruction;
- never turns an excluded weekend/holiday into a missed occurrence;
- fails closed if the exact calendar revision cannot be resolved;
- bounds candidate scanning to avoid pathological infinite searches.

Schedules without a calendar binding keep their existing trigger semantics unchanged.

### CAL-02 compatibility behavior

Schedules persisted during CAL-01 may contain a raw trigger checkpoint that falls on a
non-working date because calendar filtering did not exist yet. When such a due checkpoint
is encountered, the engine advances it to the next valid occurrence without materializing
the excluded candidate.

### CAL-02 boundary

CAL-02 only filters temporal candidates. Intrinsic business rules require a calendar-aware
trigger family.

## CAL-03 — Business-Day Trigger Semantics

`BusinessDayTrigger` models a monthly business recurrence directly:

```python
BusinessDayTrigger(ordinal=1, hour=8)  # first working day
BusinessDayTrigger(ordinal=2, hour=9)  # second working day
BusinessDayTrigger(ordinal=-1, hour=18)  # last working day
```

Positive ordinals count from the beginning of the month; negative ordinals count from the
end. The exact bound `BusinessCalendar` determines which dates are working dates, including
holidays and explicit extra working days.

The Schedule still owns the timezone and exact `CalendarSnapshotRef`. The trigger performs
no provider I/O. `CalendarOccurrencePlanner` resolves the distinction between pure temporal
triggers and calendar-aware triggers while keeping `SchedulerEngine` independent of concrete
trigger types.

Local civil time is resolved through the Schedule timezone with the same explicit ambiguous
and nonexistent-time policies already used by Cron. Monthly search is bounded.

### CAL-03 boundary

CAL-03 ships the business-day recurrence semantics, not persistence migration guarantees or
remote calendar-provider adapters.

## CAL-04 — Persistence / Migration Parity

Calendar-aware schedules now use an explicit serialized-configuration migration contract.

Schedule definitions are written as codec **v3**. Their Trigger payload is independently
versioned with `schema_version=1` and a declarative `config` object.

The decoder continues to read:

- Schedule-definition v1 without calendar binding;
- Schedule-definition v2 with the legacy flat Trigger shape;
- current v3 with the versioned Trigger envelope.

Supported legacy definitions normalize into current domain objects and are written back only
in the latest format. Unsupported future Schedule-definition or Trigger versions fail
closed.

CAL-04 also qualifies real SQLite and PostgreSQL rows containing legacy v2
`BusinessDayTrigger` + `CalendarSnapshotRef` payloads. Loading preserves the definition;
the next normal write upgrades the JSON to v3 without changing the SQL schema.

### CAL-04 boundary

This is a serialized domain-configuration migration. It deliberately does not introduce a
database schema migration because no table or column change is required.

## Non-goals

The calendar series still does **not** yet:

- ship country-specific holiday truth;
- call external calendar APIs;
- implement a SQL/File/HTTP CalendarProvider.

Those belong to later calendar lots.

## Next calendar lots

Proposed sequence:

```text
CAL-00 Calendar Foundations            ✅
CAL-01 Schedule Calendar Binding       ✅
CAL-02 Calendar-aware Occurrence Planning  ✅
CAL-03 Business-Day Trigger Semantics        ✅
CAL-04 Persistence / Migration Parity         🚧 current
CAL-05 Calendar Provider Adapters              ⏭ next
```

The exact order after CAL-02 may be refined as occurrence semantics are qualified.

---

**Status:** CAL-04 — Persistence / Migration Parity in qualification. Next: CAL-05.
