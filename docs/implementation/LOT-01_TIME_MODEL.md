# LOT-01 — Time Model

## Goal

Implement the smallest explicit temporal model needed by PyScheduleKit before any Trigger or Schedule logic exists.

## Domain objects

- `Instant`
- `Duration`
- `Timezone`
- `TimeWindow`
- `GracePeriod`

## Ports

- `Clock`

## Adapters

Production:

- `SystemClock`

Testing:

- `FixedClock`
- `MutableClock`

## Semantic decisions

### Instant

An `Instant` is an absolute point on the timeline.

- timezone-naive datetimes are rejected;
- values are normalized to UTC;
- equality compares absolute instants, not input representations.

### Duration

A `Duration` is non-negative elapsed time.

`Duration.days(1)` means exactly 24 elapsed hours. It does not mean “same local clock time tomorrow”.

### Timezone

`Timezone` stores an IANA timezone identifier using Python's `zoneinfo`.

Civil-time resolution is explicit:

- nonexistent DST local time → rejected;
- ambiguous DST local time → caller must select `fold=0` or `fold=1`.

This prevents default timezone behavior from silently deciding scheduling semantics.

### TimeWindow

Time windows are half-open:

```text
[start, end)
```

The start is included and the end is excluded.

### GracePeriod

A `GracePeriod` is a non-negative duration that derives an eligibility deadline from a scheduled `Instant`. Misfire behavior itself remains deferred.

## Architecture

```text
domain
  Instant / Duration / Timezone
          ▲
          │
ports     Clock
          ▲
          │
infrastructure
          SystemClock
```

The domain never reads the host wall clock.

Deterministic clocks live in `pyschedulekit.testing` and implement the same structural `Clock` contract.

## Qualification mapping

LOT-01 maps to:

- `T-TIME-001` — timezone-aware Instant;
- `T-TIME-002` — naive datetime rejection;
- `T-TIME-003` — equivalent absolute instants;
- `T-TIME-004` — IANA timezone versus fixed offset;
- `T-TIME-005` — 24 elapsed hours versus civil day;
- `T-TIME-006` — deterministic fixed clock;
- `T-TIME-007` — explicit mutable-clock progression;
- `T-TIME-008` — UTC normalization and host independence;
- `T-TIME-009` — half-open TimeWindow;
- `T-TIME-010` — nonexistent DST local time;
- `T-TIME-011` — ambiguous DST local time;
- `T-TIME-012` — leap day.

Additional tests qualify non-negative durations, valid windows, GracePeriod deadlines, and the SystemClock adapter.

## Intentionally deferred

LOT-01 does not implement:

- Trigger;
- recurrence;
- Cron parsing;
- MisfirePolicy;
- CalendarProvider;
- monotonic sleeping;
- SchedulerRuntime.

These belong to later lots.

## Exit criteria

- temporal Value Objects are immutable;
- no naive Instant can enter the model;
- host wall-clock access remains outside the domain;
- DST ambiguity/nonexistence is explicit;
- deterministic clocks are available to future Trigger tests;
- all T-TIME tests are green.

## Next

`LOT-02 — Trigger Foundations`
