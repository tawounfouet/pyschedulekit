# LOT-04 — CronTrigger

## Goal

Add a calendar-based recurring Trigger without introducing hidden clock access, unsafe parsing, or ambiguous timezone behavior.

The V1 contract is:

```text
minute hour day-of-month month day-of-week
```

exactly five fields.

## Why Cron is different from Interval

`IntervalTrigger` operates on elapsed duration:

```text
anchor + n × duration
```

`CronTrigger` operates on civil calendar rules:

```text
09:00 every weekday in Europe/Paris
```

These are not equivalent.

A 24-hour Interval does not mean "every day at 09:00 local time" across DST transitions.

## Syntax supported in V1

Each numeric field supports:

- wildcard: `*`;
- single value: `5`;
- list: `1,3,5`;
- range: `1-5`;
- step: `*/15`;
- stepped range: `10-50/10`;
- value-with-step: `5/15`.

Fields:

| Field | Range |
|---|---:|
| minute | 0..59 |
| hour | 0..23 |
| day-of-month | 1..31 |
| month | 1..12 |
| day-of-week | 0..7 |

For day-of-week:

```text
0 = Sunday
7 = Sunday
1 = Monday
...
6 = Saturday
```

Names such as `MON` or `JAN` are intentionally not supported in V1.

## Dialect

LOT-04 explicitly models:

```python
CronDialect.VIXIE
```

Under Vixie semantics:

- when day-of-month is wildcard, day-of-week controls matching;
- when day-of-week is wildcard, day-of-month controls matching;
- when both are restricted, either may match.

Example:

```text
0 9 13 * 1
```

means:

```text
09:00 on every Monday
OR
09:00 on the 13th day of the month
```

This behavior is tested explicitly because Cron dialect differences are a common source of production mistakes.

## Explicit timezone

A CronTrigger requires:

```python
timezone=Timezone("Europe/Paris")
```

The Trigger converts the absolute reference Instant into that local timezone, evaluates calendar candidates there, then resolves the selected civil time back into an absolute Instant.

Cron does not read:

- system timezone;
- process locale;
- ambient clock.

## Public Scheduler timezone consistency

When a CronTrigger is passed to:

```python
scheduler.add_schedule(...)
```

its timezone becomes the effective Schedule timezone unless one is explicitly supplied.

If both are supplied and differ:

```text
CronTrigger timezone != Schedule timezone
```

the operation fails immediately.

PyScheduleKit does not persist contradictory timezone metadata.

## DST gap policy

A local time may not exist when clocks move forward.

Example in Europe/Paris:

```text
2026-03-29 02:30
```

does not exist.

Default:

```python
CronNonexistentTimePolicy.SKIP
```

The nonexistent candidate is skipped and lookup continues to the next valid calendar occurrence.

Optional strict mode:

```python
CronNonexistentTimePolicy.RAISE
```

surfaces `NonexistentLocalTimeError`.

## DST fold policy

A local time may occur twice when clocks move backward.

Default:

```python
CronAmbiguousTimePolicy.FIRST
```

selects fold 0, the first occurrence.

Alternative:

```python
CronAmbiguousTimePolicy.SECOND
```

selects fold 1.

Strict mode:

```python
CronAmbiguousTimePolicy.RAISE
```

surfaces `AmbiguousLocalTimeError`.

Therefore DST behavior is never guessed invisibly.

## Strict next-after semantics

Like every Trigger:

```python
trigger.next_after(reference)
```

must return:

```text
candidate > reference
```

never equal to the reference.

For:

```text
0 9 * * *
```

at exactly 09:00, the next occurrence is the next valid day at 09:00.

## Bounded lookup

Cron evaluation must not search forever.

LOT-04 walks candidate calendar dates for at most:

```text
8 Gregorian years
```

and evaluates only configured hour/minute combinations for matching dates.

It does not replay every historical minute.

The eight-year horizon covers the longest relevant leap-day gap around non-leap century years.

If no valid occurrence exists inside the horizon:

```text
CronSearchLimitError
```

is raised.

Example of an impossible calendar expression:

```text
0 0 31 2 *
```

## Parsing security

The parser is implemented inside the domain and accepts only the documented numeric grammar.

It performs no:

- eval;
- exec;
- dynamic import;
- plugin resolution;
- arbitrary object construction.

Invalid expressions fail fast with:

```text
InvalidCronExpressionError
```

## Examples

Every weekday at 09:00 Paris time:

```python
CronTrigger(
    "0 9 * * 1-5",
    timezone=Timezone("Europe/Paris"),
)
```

Every 15 minutes during office hours:

```python
CronTrigger(
    "*/15 9-17 * * 1-5",
    timezone=Timezone("Europe/Paris"),
)
```

At noon on leap day:

```python
CronTrigger(
    "0 12 29 2 *",
    timezone=Timezone("UTC"),
)
```

## End-to-end qualification

LOT-04 is not qualified only as an isolated parser.

It is exercised through the public vertical slice:

```text
CronTrigger
    ↓
Schedule
    ↓
Scheduler.run_pending()
    ↓
ExecutionRequest
    ↓
Execution
    ↓
Attempt
    ↓
LocalExecutor
    ↓
Python callable
```

A weekday 09:00 Europe/Paris Cron schedule is proven to execute at the corresponding absolute UTC Instant.

## Qualification scenarios

LOT-04 proves:

- strict next-after semantics;
- wildcard;
- lists;
- ranges;
- steps;
- Sunday 0 and 7 equivalence;
- Vixie DOM/DOW OR semantics;
- authoritative DOM when DOW wildcard;
- authoritative DOW when DOM wildcard;
- leap-day lookup;
- timezone-to-Instant conversion;
- DST gap skip;
- DST gap strict raise;
- DST fold first occurrence;
- DST fold second occurrence;
- DST fold strict raise;
- malformed-field rejection;
- out-of-range rejection;
- zero-step rejection;
- reversed-range rejection;
- non-numeric rejection;
- impossible-expression bounded failure;
- common Trigger contract determinism/progression;
- public Scheduler end-to-end execution;
- Schedule/Cron timezone mismatch rejection.

## Non-goals

V1 does not support:

- six-field or seconds Cron;
- year field;
- named months;
- named weekdays;
- aliases such as `@daily`;
- Quartz `?`;
- Quartz `L` / `W` / `#`;
- locale-dependent names;
- arbitrary Cron dialect plugins.

These can be introduced only with explicit semantics and tests.

## Architecture progression

```text
DateTrigger       ✅
IntervalTrigger   ✅
CronTrigger       ✅
      │
      ▼
Trigger family complete for V1
      │
      ▼
next capability wave:
Misfire → Catch-Up → Concurrency → Retry
```

## Exit criteria

LOT-04 is complete when:

- Cron is a pure deterministic Trigger;
- timezone is explicit;
- DST behavior is explicit;
- parser grammar is bounded and safe;
- Vixie semantics are tested;
- impossible schedules do not loop forever;
- Cron works through public run_pending();
- all Python quality gates are green.

## Next

`LOT-12 — Misfire Policy Foundations`
