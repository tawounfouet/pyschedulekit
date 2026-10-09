# CMP-00 — Composite Trigger Contract

## Objective

Establish the smallest deterministic composite-trigger primitive before adding persistence,
public API or calendar-aware composition.

CMP-00 introduces the domain-internal `AnyOfTrigger`. It represents the temporal union of
two or more ordinary `Trigger` children.

```text
Trigger A ─┐
           ├─ earliest candidate strictly after reference ─> AnyOfTrigger
Trigger B ─┘
```

## Contract

For one absolute reference Instant, `AnyOfTrigger`:

1. asks every child for its first candidate strictly after the same reference;
2. ignores exhausted children;
3. returns the earliest remaining candidate;
4. returns `None` only when every child is exhausted;
5. emits a shared candidate once when several children produce the same Instant;
6. propagates child lookup failures unchanged;
7. fails closed when a child returns a non-Instant or a non-progressing candidate.

At least two children are required. A single child is already a complete Trigger and does
not need a composite wrapper.

## Determinism

The selected candidate is independent of child order:

```text
AnyOf(A, B).next_after(t) == AnyOf(B, A).next_after(t)
```

for conforming deterministic children. Stored child order is preserved as configuration,
but does not act as a tie-breaker for occurrence time.

## Deliberate boundary

CMP-00 accepts pure temporal `Trigger` children only. `CalendarAwareTrigger` children are
excluded because they require an explicit rule for calendar resolution across the complete
composite tree.

CMP-00 does not add:

- stable public imports;
- SQL codec support;
- persisted-format migration;
- Schedule or Scheduler end-to-end qualification;
- intersection / `AllOf` semantics;
- calendar-aware nested children.

These guarantees are added incrementally only after the domain union contract is proven.

## Acceptance guarantees

- construction rejects fewer than two children;
- construction rejects objects outside the `Trigger` protocol;
- earliest-candidate selection is order-independent;
- finite and recurring children may be combined;
- simultaneous child candidates are deduplicated;
- exhaustion is deterministic;
- invalid child output fails closed;
- child exceptions are not hidden or reclassified;
- the composite is immutable and satisfies the reusable Trigger contract suite.

---

**Status:** CMP-00 — Composite Trigger Contract implemented and locally qualified.
