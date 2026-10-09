# 0.4.x — Composite Trigger Foundations

PyScheduleKit's next pre-1.0 roadmap axis builds deterministic trigger composition on top of
the completed calendar sequence.

## Planned sequence

```text
CMP-00 Composite Trigger Contract                 COMPLETE
CMP-01 AnyOf Occurrence Planning                  COMPLETE
CMP-02 Checkpoints, Deduplication and Bounds      COMPLETE
CMP-03 Versioned Codec and Migration              PLANNED
CMP-04 Persistence Adapter Parity                 PLANNED
CMP-05 Public API, E2E, Documentation, Benchmark  PLANNED
```

## Why union first

The union of child occurrence streams has one precise rule:

```text
next(any children) = minimum(next(each child))
```

This can be implemented without hidden wall-clock access, I/O or a new runtime dependency.
It also provides immediate value for schedules that should run on either of several temporal
rules.

## Why intersection is deferred

A generic intersection may be empty or require unbounded search when independent recurrence
rules never converge. PyScheduleKit will not expose `AllOfTrigger` until it has explicit
termination, search-bound and failure semantics.

## Roadmap rules

Each CMP lot must preserve:

- strict `next_after()` progression;
- deterministic replay from persisted configuration and checkpoints;
- duplicate suppression for shared candidate Instants;
- compatibility with catch-up and coalescing;
- parity across InMemory, SQLite and PostgreSQL before stable public exposure;
- zero runtime dependencies.

CMP-01 intentionally remains domain-internal. Public API exposure follows only after codec,
migration and adapter-parity guarantees are executable.

---

**Status:** CMP-00 through CMP-02 complete; CMP-03 is the next planned composite-trigger lot.
