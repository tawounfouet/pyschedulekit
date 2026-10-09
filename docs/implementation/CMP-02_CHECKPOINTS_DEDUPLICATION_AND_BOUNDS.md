# CMP-02 — Checkpoints, Deduplication and Bounds

## Objective

Harden composite scheduling under nested configuration and recovery policies before any
persisted or public representation is introduced.

## Associative normalization

Nested unions are normalized at construction:

```text
AnyOf(AnyOf(A, B), C)
          ↓
AnyOf(A, B, C)
```

Union is associative, so flattening preserves occurrence semantics while removing recursive
lookup depth and giving one explicit fan-out boundary.

Stored child order remains stable. Candidate selection remains independent of that order.

## Fan-out bound

One `next_after()` call asks each flattened child for one candidate. CMP-02 limits a
composite to 64 flattened children, making the maximum orchestration work explicit:

```text
lookup work <= 64 child lookups
```

The bound is applied after nested unions are flattened, so nesting cannot bypass it.

## Checkpoint model

`AnyOfTrigger` remains stateless. The Schedule's last emitted absolute Instant is the only
checkpoint required:

```text
last emitted Instant
        ↓
same strict reference sent to every child
        ↓
earliest strictly-later child candidate
```

When children share an Instant, the next lookup uses that shared Instant as the strict
reference for every child. The duplicate therefore cannot reappear.

## SchedulerEngine qualification

CMP-02 proves through the real application engine that:

- one shared child Instant creates one durable ExecutionRequest;
- catch-up reconstructs the ordered unique union;
- catch-up respects `max_occurrences`, reports remaining work and advances to the first
  unprocessed checkpoint;
- coalescing selects the latest unique due occurrence;
- bounded coalescing reports an incomplete backlog without advancing because the latest due
  occurrence is not yet known;
- Schedule checkpoint advancement remains correct after each policy.

## Deliberate boundary

CMP-02 still does not add:

- stable public imports;
- persisted codec support;
- database adapter parity;
- calendar-aware nested children;
- intersection semantics.

## Acceptance guarantees

- nested unions are flattened deterministically;
- at most 64 flattened children are accepted;
- nesting cannot evade the child bound;
- one shared Instant creates one request;
- catch-up and coalescing remain duplicate-free;
- catch-up and coalescing recovery limits preserve resumable Schedule checkpoints.

---

**Status:** CMP-02 — Checkpoints, Deduplication and Bounds implemented and locally qualified.
