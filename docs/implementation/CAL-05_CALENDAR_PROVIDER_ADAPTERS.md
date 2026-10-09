# CAL-05 — Calendar Provider Adapters

## Objective

Add durable and deployable CalendarProvider adapters without moving calendar semantics or
holiday truth into the scheduler core.

CAL-00 established the port. CAL-05 adds two deterministic local adapters:

- `FileCalendarProvider`;
- `SqliteCalendarProvider`.

A remote HTTP/SaaS provider remains deliberately out of scope because transient I/O
failures require a separate SchedulerEvaluationError/runtime suppression contract.

## Shared strict codec

Both adapters use the same versioned BusinessCalendar JSON definition.

One calendar revision:

```json
{
  "schema_version": 1,
  "reference": "finance-days",
  "revision": 3,
  "working_weekdays": [0, 1, 2, 3, 4],
  "holidays": ["2026-01-01"],
  "extra_working_days": ["2026-01-10"]
}
```

The codec:

- rejects unknown fields;
- rejects missing fields;
- rejects unsupported future schema versions;
- validates ISO dates;
- rebuilds normal domain `BusinessCalendar` objects;
- serializes deterministically.

No arbitrary class name, import path, callable or provider implementation is encoded.

## FileCalendarProvider

The file adapter consumes a collection:

```json
{
  "schema_version": 1,
  "calendars": [
    {
      "schema_version": 1,
      "reference": "finance-days",
      "revision": 1,
      "working_weekdays": [0, 1, 2, 3, 4],
      "holidays": [],
      "extra_working_days": []
    }
  ]
}
```

The provider loads the complete file **once at construction**.

This is deliberate:

```text
provider construction
→ validated immutable snapshot
→ deterministic resolve()
```

Changing the file on disk does not mutate an already-running Scheduler. Adopting a new file
requires constructing a new provider explicitly.

The file must be UTF-8 and is bounded by a configurable byte-size limit.

## SqliteCalendarProvider

The SQLite adapter owns a small isolated schema:

```text
pyschedulekit_calendar_schema
pyschedulekit_business_calendars
```

It does not reuse or overload Schedule runtime tables.

Identity is:

```text
(CalendarRef, CalendarRevision)
```

The adapter supports:

- explicit `register(calendar)`;
- explicit `replace=True` for a duplicate revision;
- latest revision resolution;
- exact historical revision resolution;
- deterministic reference enumeration;
- fail-closed provider schema versioning.

The provider requires a file-backed SQLite database. `:memory:` is rejected because
separate connections would make persistence semantics surprising.

## Coexistence with Scheduler SQLite persistence

The calendar-provider tables use dedicated names and metadata. Therefore:

```python
database = "scheduler.db"

Scheduler(
    uow_factory=SqliteUnitOfWorkFactory(database),
    calendar_provider=SqliteCalendarProvider(database),
)
```

is supported and qualified.

This allows one deployment file while keeping the two persistence models conceptually
separate.

## Error contract

Static configuration problems remain `PyScheduleKitConfigurationError`:

- missing file;
- malformed JSON;
- unknown calendar;
- unknown exact revision;
- duplicate revision without `replace=True`;
- unsupported file/calendar/provider schema version.

Low-level SQLite operational failures are wrapped as runtime storage failures rather than
misclassified as static calendar absence.

## Determinism

Exact Schedule bindings remain unchanged:

```text
ScheduleDefinition.calendar
=
CalendarSnapshotRef(reference, revision)
```

The adapter only resolves that reference to the immutable definition. The provider never
rewrites the Schedule to "latest".

## Acceptance guarantees

1. File and SQLite adapters satisfy the CalendarProvider protocol;
2. exact and latest revision resolution match InMemory behavior;
3. file state is immutable after provider construction;
4. malformed/unknown/future JSON fails closed;
5. duplicate file revisions are rejected;
6. SQLite revisions survive provider reconstruction;
7. duplicate SQLite writes require explicit replacement;
8. future SQLite provider schema versions fail closed;
9. public Scheduler consumes both adapters unchanged;
10. SqliteCalendarProvider can coexist with SqliteUnitOfWorkFactory in one database;
11. no runtime third-party dependency is added;
12. remote HTTP/holiday SaaS behavior remains out of scope.

## Non-goals

CAL-05 does not add:

- automatic country holiday datasets;
- HTTP CalendarProvider;
- external SaaS credentials or secrets;
- background file watching;
- automatic provider refresh;
- cross-process cache invalidation.

Those require separate runtime/error/operational contracts.
