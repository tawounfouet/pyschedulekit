# LOT-02 — Trigger Foundations

## Goal

Define the smallest common contract that every temporal trigger in PyScheduleKit must satisfy before introducing concrete trigger implementations.

## Core contract

```python
class Trigger(Protocol):
    def next_after(self, reference: Instant) -> Instant | None: ...
```

The contract answers one question only:

> Given an absolute reference Instant, what is the next candidate occurrence strictly after it?

## Semantics

A conforming Trigger must be:

- deterministic for the same input;
- strictly progressive when it returns an Instant;
- free from hidden Clock access;
- free from I/O;
- independent from scheduler runtime state;
- able to represent exhaustion by returning `None`.

## Why `None` for exhaustion?

LOT-02 intentionally does not introduce a `TriggerExhausted` sentinel object.

The absence of a next candidate is already represented naturally by:

```python
Instant | None
```

This keeps the core contract small and allows finite triggers such as a future `DateTrigger` to terminate without introducing an artificial domain entity.

## Why no TriggerKind yet?

`TriggerKind` is intentionally deferred until concrete built-in triggers and serialization actually need stable discriminators.

Introducing values such as:

```text
DATE
INTERVAL
CRON
```

before those implementations exist would freeze a taxonomy earlier than necessary.

The later serialization layer will own stable persisted discriminators.

## TriggerContractSuite

LOT-02 introduces a reusable testing utility:

```python
TriggerContractSuite.assert_conforms(trigger, references)
```

It currently proves two universal invariants:

1. deterministic result for identical reference Instants;
2. every returned candidate is strictly greater than its reference.

Concrete trigger lots will reuse this suite and add trigger-specific properties.

## Bounded evaluation

The common protocol cannot mechanically prove that arbitrary user code terminates.

Therefore bounded evaluation is treated as a concrete implementation requirement:

- IntervalTrigger must compute directly rather than scan occurrence-by-occurrence;
- CronTrigger must use an explicit search horizon;
- future custom triggers must document their own bound.

## Architecture

```text
Instant
  ▲
  │
Trigger.next_after(reference)
  │
  ▼
Instant | None
```

No Clock is passed to Trigger.

The Scheduler or planner will capture "now" elsewhere and explicitly pass an Instant as the reference.

This keeps Trigger evaluation:

- deterministic;
- replayable;
- testable;
- independent from ambient time.

## Qualification

LOT-02 proves:

- Trigger is a structural protocol;
- next_after returns the first candidate strictly after the reference;
- `None` is the exhaustion representation;
- conforming deterministic triggers pass the shared suite;
- non-progressing triggers are rejected by the suite;
- non-deterministic triggers are rejected by the suite;
- no Clock or Runtime context is required by the Trigger contract.

## Intentionally deferred

LOT-02 does not implement:

- DateTrigger;
- IntervalTrigger;
- CronTrigger;
- Trigger serialization;
- TriggerKind;
- Calendar filtering;
- ScheduleWindow filtering;
- occurrence materialization.

## Exit criteria

- the Trigger protocol is stable enough for first built-ins;
- the contract does not depend on Runtime or Clock;
- deterministic/progression invariants have executable assertions;
- exhaustion semantics are explicit;
- no speculative trigger taxonomy has been frozen.

## Next

`LOT-03 — DateTrigger & IntervalTrigger`
