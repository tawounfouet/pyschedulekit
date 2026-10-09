# CMP-03 — Versioned Codec and Migration

## Objective

Persist `AnyOfTrigger` declaratively without changing the Schedule-definition SQL schema or
weakening existing version boundaries.

## Persisted shape

The Schedule-definition codec remains version 3. `AnyOfTrigger` is encoded as a Trigger
kind whose children each carry their own versioned Trigger envelope:

```json
{
  "kind": "any_of",
  "schema_version": 1,
  "config": {
    "children": [
      {
        "kind": "date",
        "schema_version": 1,
        "config": {"at": "2026-01-01T10:00:00+00:00"}
      },
      {
        "kind": "interval",
        "schema_version": 1,
        "config": {
          "anchor": "2026-01-01T10:00:00+00:00",
          "every_seconds": 900.0
        }
      }
    ]
  }
}
```

No class name, import path, callable or executable payload is persisted.

## Version contract

- Schedule definitions remain codec v3;
- the `any_of` Trigger config starts at schema version 1;
- every child must use a versioned Trigger envelope;
- unsupported parent or child versions fail closed;
- existing Date, Interval, Cron and BusinessDay payloads are unchanged.

Adding a new Trigger kind does not require a Schedule codec bump because v3 already defines
an independently versioned Trigger envelope.

## Canonical migration

The decoder accepts a bounded nested `any_of` payload. Domain construction flattens the
associative union, and the next normal encode writes one canonical flat child list:

```text
persisted AnyOf(AnyOf(A, B), C)
              ↓ decode
domain AnyOf(A, B, C)
              ↓ encode
persisted AnyOf(A, B, C)
```

Occurrence semantics are qualified before and after migration.

## Defensive decoding

The codec rejects:

- non-array `children`;
- non-object child payloads;
- fewer than two children;
- more than 64 flattened children;
- unversioned children;
- unsupported future child versions;
- calendar-aware children;
- unknown `any_of` config fields;
- nesting deeper than 16 composite levels.

The nesting bound protects decoding before domain flattening can enforce the fan-out bound.

## Deliberate boundary

CMP-03 provides the shared SQL definition codec used by SQLite and PostgreSQL, but live-row
round trips, adapter parity and upgrade-on-write qualification remain CMP-04 work.

`AnyOfTrigger` also remains outside the stable public API until CMP-05.

## Acceptance guarantees

- encoded child order is deterministic and preserved;
- all child payloads are independently versioned;
- decode/encode round trips preserve domain equality;
- nested payload migration produces canonical flat JSON;
- migration preserves occurrence sequences;
- malformed, future or unsafe payloads fail closed;
- no SQL table or column migration is required.

---

**Status:** CMP-03 — Versioned Codec and Migration implemented and locally qualified.
