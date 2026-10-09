# CMP-04 — Persistence Adapter Parity

## Objective

Qualify the CMP-03 composite codec through the real InMemory, SQLite and PostgreSQL Schedule
repositories before exposing `AnyOfTrigger` publicly.

## Shared adapter contract

The same test now targets every configured adapter:

```text
AnyOfTrigger definition + Schedule checkpoint
                    ↓ commit
       InMemory / SQLite / PostgreSQL
                    ↓ reopen
same definition + same next_run_time
                    ↓ advance + commit + reopen
same next unique union checkpoint
```

This proves that the composite is not merely codec-round-trippable in isolation: it survives
the repository identity map, transaction boundary, optimistic persistence version and a
fresh UnitOfWork.

## SQL normalization

SQLite and PostgreSQL are also seeded with a valid but non-canonical nested composite row:

```text
persisted AnyOf(AnyOf(A, B), C)
             ↓ repository load
domain AnyOf(A, B, C)
             ↓ normal Schedule write
persisted AnyOf(A, B, C)
```

The test asserts semantic equality on load and canonical flat JSON after the next normal
write. No dedicated migration command or SQL DDL change is required.

## Qualified adapters

- InMemory — definition and checkpoint round trip;
- SQLite — definition/checkpoint round trip plus nested-row normalization;
- PostgreSQL 16 — same shared contract in CI;
- PostgreSQL 17 — same shared contract in CI;
- PostgreSQL 18 — same shared contract in CI.

## Deliberate boundary

CMP-04 does not yet add:

- stable root or `pyschedulekit.api` exports;
- public Scheduler E2E examples;
- public API reference documentation;
- composite benchmark evidence.

Those are the final CMP-05 graduation gates.

## Acceptance guarantees

- all adapters preserve composite Schedule definitions;
- all adapters preserve and advance the duplicate-free checkpoint identically;
- fresh UnitOfWork instances reconstruct the same domain trigger;
- SQLite and PostgreSQL accept bounded nested composite rows;
- the next normal SQL write canonicalizes nested payloads;
- no SQL table or column migration is introduced;
- the base package remains free of runtime dependencies.

---

**Status:** CMP-04 — Persistence Adapter Parity implemented and locally qualified; live
PostgreSQL versions are qualified in CI.
