# 0.3.x — Calendar Foundations

CAL-00 introduces the temporal calendar abstractions that were specified from the beginning
but intentionally deferred until the core scheduler, persistence and execution ecosystem
were mature.

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

## Non-goals

CAL-00 does **not** yet:

- add `CalendarSnapshotRef` to `ScheduleDefinition`;
- change the SQLite/PostgreSQL schema;
- filter Cron/Interval/Date trigger occurrences through a calendar;
- implement "first/last working day" triggers;
- ship country-specific holiday truth;
- call external calendar APIs;
- implement a SQL/File/HTTP CalendarProvider.

Those belong to later calendar lots.

## Next calendar lots

Proposed sequence:

```text
CAL-00 Calendar Foundations            ← current
CAL-01 Schedule Calendar Binding
CAL-02 Calendar-aware Occurrence Planning
CAL-03 Business-Day Trigger Semantics
CAL-04 Persistence / Migration Parity
CAL-05 Calendar Provider Adapters
```

The exact order after CAL-02 may be refined once Schedule binding is qualified.

---

**Status:** CAL-00 — Calendar Foundations.
