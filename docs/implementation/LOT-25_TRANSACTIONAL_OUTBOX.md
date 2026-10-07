# LOT-25 — Transactional Outbox

## Goal

Persist integration intent atomically with scheduler state, then publish that intent separately.

The core guarantee is:

```text
business state change
        +
outbox message
        ↓
same UnitOfWork
        ↓
same database transaction
```

External publication happens only after that transaction commits.

## Why an outbox

Without an outbox, this sequence is unsafe:

```text
commit scheduler state
        ↓
publish external event
        ↓
process crashes between the two
```

The scheduler state may be durable while the integration event is permanently lost.

The reverse ordering is also unsafe:

```text
publish external event
        ↓
commit scheduler state
        ↓
database commit fails
```

An external consumer may observe an event for state that never committed.

LOT-25 removes that dual-write gap.

## Durable model

`OutboxMessage` contains:

```text
id
event_type
aggregate_type
aggregate_id
payload
created_at
state
published_at
publish_attempts
last_error
version
```

States:

```text
PENDING
   ↓ successful publication + local acknowledgement
PUBLISHED
```

Publication failure leaves the message `PENDING`.

## Deterministic identity

Message identity is derived from:

```text
event_type
+
aggregate_type
+
aggregate_id
```

This provides a stable integration identity for one lifecycle fact.

Consumers should use:

```text
OutboxMessage.id
```

as their idempotency key.

## At-least-once semantics

LOT-25 intentionally guarantees **at-least-once**, not exactly-once.

The dispatcher performs:

```text
load committed PENDING message
        ↓
publish externally
        ↓
reload message
        ↓
mark PUBLISHED
        ↓
commit acknowledgement
```

If the process crashes after the external publish but before the local acknowledgement:

```text
external side effect happened
+
message remains PENDING
        ↓
message may be published again
```

This is expected.

Consumers must deduplicate using the stable message ID.

## External publisher port

Transport integration is abstracted behind:

```python
class OutboxPublisher(Protocol):
    def publish(self, message: OutboxMessage) -> None: ...
```

LOT-25 therefore has no Kafka, RabbitMQ, HTTP, cloud-bus, or vendor dependency.

A future adapter can implement any of those transports.

## Explicit dispatch

Publication is intentionally separate from `run_pending()`.

Public API:

```python
result = scheduler.dispatch_outbox(
    publisher,
    limit=100,
)
```

This allows deployments to choose:

- a dedicated publisher worker;
- periodic publication;
- publication after scheduler cycles;
- transport-specific scaling.

The scheduler execution transaction never waits on an external broker.

## Lifecycle messages

LOT-25 initially emits execution lifecycle messages with clear external value.

### Attempt started

When an Attempt becomes RUNNING:

```text
Execution RUNNING
Attempt RUNNING
OutboxMessage execution.attempt.started
```

All three are committed atomically.

### Attempt completed

For:

```text
SUCCESS
FAILED
TIMED_OUT
CANCELLED
```

the Attempt, Execution, and:

```text
execution.attempt.completed
```

message are committed in the same transaction.

### Cancellation

Idle cancellation produces:

```text
execution.cancelled
```

Running cancellation intent produces:

```text
execution.cancellation.requested
```

### Crash recovery

LOT-23 recovery also emits:

```text
execution.attempt.completed
```

inside the same recovery transaction when an orphaned Attempt is converted to FAILED or CANCELLED.

Crash recovery therefore does not create an integration blind spot.

## Failure recording

If a publisher raises:

```text
message remains PENDING
publish_attempts += 1
last_error = normalized error
```

The next dispatcher pass retries the same message ID.

When publication later succeeds:

```text
state = PUBLISHED
publish_attempts += 1
last_error = NULL
published_at = now
```

## Ordering

Pending messages are selected by:

```text
created_at ASC
id ASC
```

This provides deterministic local dispatch order.

LOT-25 does not claim globally ordered delivery across multiple future workers.

## UnitOfWork integration

The persistence contract now includes:

```text
uow.schedules
uow.requests
uow.executions
uow.attempts
uow.outbox
```

In-memory and SQLite adapters preserve the same staged write semantics.

```text
add/save business state
add outbox message
        ↓
commit()
        ↓
validate all repositories
        ↓
apply all repositories
        ↓
one transaction
```

A duplicate or invalid outbox write rolls back earlier business writes in the same UnitOfWork.

## SQLite schema v3

LOT-25 introduces:

```text
SCHEMA_VERSION = 3
```

and:

```text
outbox_messages
```

with an index on:

```text
(state, created_at, id)
```

for pending-message scans.

Schema transitions:

```text
new database → v3
v2 database  → v3
v1 database  → v2 → v3
```

Existing scheduler data is preserved.

## Optimistic concurrency

Outbox acknowledgements and failure records use the same versioned CAS semantics as other durable entities:

```sql
UPDATE outbox_messages
SET ...
WHERE id = ?
  AND version = ?
```

A stale acknowledgement cannot silently overwrite newer message state.

## Safety properties

1. outbox intent is committed atomically with lifecycle state;
2. no external broker call occurs inside the business transaction;
3. publication failures never roll back already committed scheduler state;
4. failed publication remains retryable;
5. successful publication is acknowledged durably;
6. stable message IDs support consumer deduplication;
7. crash-after-publish may duplicate delivery and is documented;
8. ordering is deterministic within one pending scan;
9. crash recovery emits lifecycle messages transactionally;
10. both persistence adapters implement the same outbox port.

## Qualification

LOT-25 qualifies:

- deterministic message identity;
- PENDING → PUBLISHED lifecycle;
- publish failure remains PENDING;
- SQLite outbox round-trip;
- duplicate outbox write rolls back business state;
- oldest-first pending selection;
- successful dispatcher acknowledgement;
- failed publish followed by successful retry;
- v2 → v3 schema migration;
- v1 → current schema migration regression;
- Scheduler Attempt start/completion messages;
- Scheduler explicit publication E2E.

## Non-goals

LOT-25 does not implement:

- exactly-once delivery;
- consumer inbox/dedup storage;
- Kafka/RabbitMQ/cloud-bus adapters;
- distributed publisher claims;
- leases or fencing;
- dead-letter queues;
- exponential publisher backoff;
- outbox retention cleanup;
- globally ordered delivery.

These operational concerns belong to Distribution and Production Maturity.

## Durability phase complete

```text
LOT-21 SQL Persistence Foundations      ✅
LOT-22 Transactions / DB Constraints    ✅
LOT-23 Crash Recovery                   ✅
LOT-24 Reconciliation                   ✅
LOT-25 Transactional Outbox             ✅
```

## Next

`LOT-26 — Distributed Claims`
