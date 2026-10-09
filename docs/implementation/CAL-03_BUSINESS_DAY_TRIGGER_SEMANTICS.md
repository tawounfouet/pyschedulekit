# CAL-03 — Business-Day Trigger Semantics

## Objective

Introduce a built-in calendar-aware recurrence whose business calendar is part of the
occurrence definition itself.

CAL-02 filters candidates produced by pure temporal triggers. CAL-03 adds a second trigger
family for rules such as:

```text
first working day of month
second working day of month
last working day of month
```

## Public model

`BusinessDayTrigger` is a monthly recurrence:

```python
BusinessDayTrigger(ordinal=1, hour=8)
BusinessDayTrigger(ordinal=2, hour=9, minute=30)
BusinessDayTrigger(ordinal=-1, hour=18)
```

Ordinal semantics:

```text
 1  = first working day from month start
 2  = second working day
...
-1  = last working day from month end
-2  = penultimate working day
```

Zero is invalid. The absolute ordinal is bounded to 31.

## Ownership of context

The trigger owns only the intrinsic recurrence rule:

```text
ordinal
local hour/minute
DST resolution policy
```

The Schedule owns:

```text
Timezone
CalendarSnapshotRef
```

The application resolves the exact immutable `BusinessCalendar` revision before domain
evaluation.

The trigger never performs provider I/O and never contains country-specific holiday truth.

## Trigger families

```text
Pure temporal Trigger
├── DateTrigger
├── IntervalTrigger
└── CronTrigger
        ↓ raw candidate
        ↓
CalendarOccurrencePlanner filters candidate

CalendarAwareTrigger
└── BusinessDayTrigger
        ↓ exact BusinessCalendar + Schedule Timezone
        ↓
CalendarOccurrencePlanner delegates intrinsic calculation
```

This preserves a single SchedulerEngine planning path without type switches in the engine.

## Calendar semantics

For one target month:

1. enumerate civil dates in the month;
2. retain dates accepted by the exact `BusinessCalendar`;
3. select the configured positive or negative ordinal;
4. combine the selected date with the trigger's local hour/minute;
5. resolve that local datetime through the Schedule timezone;
6. require the result to be strictly after the supplied reference.

Holidays, non-working weekdays and explicit extra working days therefore participate in the
intrinsic recurrence itself.

## DST policy

`BusinessDayTrigger` reuses the explicit policies already used by `CronTrigger`:

- `CronAmbiguousTimePolicy.FIRST`
- `CronAmbiguousTimePolicy.SECOND`
- `CronAmbiguousTimePolicy.RAISE`
- `CronNonexistentTimePolicy.SKIP`
- `CronNonexistentTimePolicy.RAISE`

The trigger never silently invents an offset.

## Bounded search

Monthly search is bounded to 100 years.

An impossible calendar such as one with no working dates raises
`BusinessDaySearchLimitError` instead of looping indefinitely.

## Persistence

The SQL schedule-definition codec stores a declarative trigger payload:

```json
{
  "kind": "business_day",
  "ordinal": -1,
  "hour": 18,
  "minute": 30,
  "ambiguous_time": "first",
  "nonexistent_time": "skip"
}
```

No executable code, dynamic import, provider configuration or holiday source is persisted.

The existing Schedule-definition codec version remains v2 because an older v2 runtime
encountering the new `business_day` kind fails closed with an unsupported-trigger error;
it cannot silently reinterpret or drop the trigger.

## Invariants

1. a `BusinessDayTrigger` requires a Schedule calendar binding;
2. the calendar revision must resolve exactly;
3. local civil time uses the Schedule timezone;
4. positive ordinals count from month start;
5. negative ordinals count from month end;
6. holidays and extra working days are authoritative calendar inputs;
7. occurrence lookup is strictly after the reference;
8. impossible searches are bounded;
9. persistence is declarative and deterministic;
10. SchedulerEngine remains unaware of concrete trigger types.

## Qualification

CAL-03 qualification covers:

- first, second and last working-day semantics;
- holidays;
- exceptional working Saturdays;
- timezone conversion;
- progression to the following month;
- invalid ordinals/hour/minute;
- missing calendar binding;
- bounded impossible calendars;
- nonexistent local times;
- SQL codec round-trip;
- Memory / SQLite / PostgreSQL adapter parity;
- public Scheduler end-to-end behavior.

## Non-goals

CAL-03 does not yet introduce:

- country-specific holiday datasets;
- SQL/File/HTTP calendar providers;
- weekly business-day offsets;
- arbitrary business-day arithmetic APIs;
- custom calendar-aware trigger registration.

Those belong to later calendar lots.
