# LOT-03 — DateTrigger & IntervalTrigger

## Goal

Implement the first concrete Trigger behaviors while preserving the common contract established in LOT-02.

This lot introduces:

- `DateTrigger` — one finite absolute occurrence;
- `IntervalTrigger` — fixed-rate recurrence anchored to an absolute Instant.

## DateTrigger

`DateTrigger` represents exactly one candidate occurrence.

```text
reference < at  → at
reference = at  → None
reference > at  → None
```

Because `Trigger.next_after(reference)` is strictly greater than the supplied reference, querying exactly at the scheduled Instant means the trigger is already exhausted.

### Properties

- immutable;
- deterministic;
- finite;
- no Clock access;
- no I/O;
- conforms to `Trigger` structurally.

## IntervalTrigger

`IntervalTrigger` models fixed-rate recurrence:

```text
anchor
anchor + 1 × interval
anchor + 2 × interval
anchor + 3 × interval
...
```

Its definition is:

```python
IntervalTrigger(
    every=Duration.minutes(10),
    anchor=anchor,
)
```

### Strictly positive interval

`Duration` itself may represent zero because zero elapsed time is meaningful elsewhere.

An `IntervalTrigger` cannot.

```text
every <= 0
→ invalid IntervalTrigger
```

LOT-03 therefore validates positivity at the Trigger boundary instead of weakening the general Duration model.

## Fixed-rate semantics

The recurrence is always derived from:

```text
anchor + n × interval
```

It is never derived from actual execution time.

Example:

```text
planned:
10:00
10:10
10:20

10:10 occurrence actually executes at 10:12

next occurrence:
10:20
```

Not:

```text
10:22
```

That alternative would be fixed-delay scheduling and is intentionally outside this Trigger.

## Direct calculation

When `reference >= anchor`:

```text
elapsed = reference - anchor
completed_intervals = elapsed // interval
next_index = completed_intervals + 1
candidate = anchor + next_index × interval
```

This is direct arithmetic.

The implementation does not do:

```python
while candidate <= reference:
    candidate += interval
```

Therefore a reference years in the future does not require replaying every historical occurrence.

## Before the anchor

If:

```text
reference < anchor
```

then:

```text
next_after(reference) = anchor
```

The anchor is the first valid occurrence.

## Exact boundary

If:

```text
reference == anchor + n × interval
```

then the next candidate is:

```text
anchor + (n + 1) × interval
```

This preserves the strict `next_after` contract.

## Elapsed time semantics

`IntervalTrigger` uses `Duration`.

Therefore:

```python
Duration.days(1)
```

means:

```text
24 elapsed hours
```

not:

```text
same local civil time tomorrow
```

Civil/calendar recurrence belongs to `CronTrigger` and later calendar-aware triggers.

## Qualification mapping

LOT-03 implements the relevant test matrix scenarios:

- `T-TRG-001` — DateTrigger emits one occurrence;
- `T-TRG-002` — DateTrigger exhausts at/after its occurrence;
- `T-TRG-003` — DateTrigger immutable and conforming;
- `T-TRG-010` — interval must be strictly positive;
- `T-TRG-011` — exact progression from anchor;
- `T-TRG-012` — strict progression;
- `T-TRG-013` — no cumulative drift;
- `T-TRG-014` — actual execution time does not shift recurrence;
- `T-TRG-015` — far-future calculation remains direct.

Both implementations also pass the shared `TriggerContractSuite`.

## Example

```python
anchor = Instant.parse("2026-01-01T10:00:00Z")

trigger = IntervalTrigger(
    every=Duration.minutes(10),
    anchor=anchor,
)

trigger.next_after(Instant.parse("2026-01-01T10:12:00Z"))
# → 2026-01-01T10:20:00Z
```

## Intentionally deferred

This lot does not implement:

- CronTrigger;
- fixed-delay scheduling;
- jitter;
- calendars;
- schedule windows;
- misfire;
- catch-up;
- occurrence materialization;
- serialization codecs.

## Why Cron is not next on the implementation critical path

The logical roadmap contains a Cron lot, but the implementation roadmap explicitly recommends proving the first end-to-end scheduler with `IntervalTrigger` before taking on:

- civil-time recurrence;
- DST policies;
- DOM/DOW semantics;
- Cron parser complexity.

Therefore the critical path now moves to:

```text
Date/Interval Trigger
        ↓
Schedule
        ↓
Occurrence
        ↓
InMemory Persistence
        ↓
SchedulerEngine
```

Cron remains planned and will be reintroduced once the first vertical slice is operational.

## Exit criteria

LOT-03 is complete when:

- DateTrigger is finite and deterministic;
- IntervalTrigger rejects zero intervals;
- IntervalTrigger stays anchored;
- no drift is introduced by late execution;
- far-future lookup does not scan historical occurrences;
- both triggers satisfy the common Trigger contract;
- all CI quality gates are green.

## Next

`LOT-05 — Schedule Aggregate` on the implementation critical path.

`LOT-04 — CronTrigger` remains deferred until after the first in-memory end-to-end slice.
