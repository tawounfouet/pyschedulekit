# LOT-30 — Observability

## Goal

Make the scheduler operationally inspectable without coupling PyScheduleKit to one metrics, logging, or tracing vendor.

LOT-30 introduces a dependency-neutral structured observation boundary that can later feed:

```text
Prometheus
OpenTelemetry
structured logging
custom dashboards
embedded diagnostics
```

while preserving the core rule:

> observability may describe scheduler behavior, but it must never become a scheduler correctness dependency.

## Architecture

```text
Application services
       │
       ▼
    Observer
       │
       ▼
ObservationSink port
       │
       ├── InMemoryObservationSink
       ├── Prometheus adapter        future
       ├── OpenTelemetry adapter     future
       └── logging adapter           future
```

The domain layer remains independent from observability infrastructure.

## Observation model

LOT-30 introduces the immutable `Observation` record:

```text
Observation
├── name
├── recorded_at
└── attributes
```

Attributes are deterministic, structured values:

```text
str
int
float
bool
```

They are intentionally bounded and vendor-neutral.

## Port

External adapters implement:

```python
class ObservationSink(Protocol):
    def record(self, observation: Observation) -> None: ...
```

PyScheduleKit does not require a concrete monitoring dependency.

## Best-effort delivery

`Observer` isolates sink failures:

```text
business operation succeeds
        │
        ▼
emit observation
        │
        ├── sink succeeds → telemetry retained
        │
        └── sink fails    → scheduler continues
```

This means an unavailable metrics backend cannot:

- prevent Schedule materialization;
- fail an Attempt;
- roll back durable state;
- stop the continuous runtime.

## Reference adapter

`InMemoryObservationSink` is a thread-safe built-in adapter intended for:

- tests;
- embedded applications;
- diagnostics;
- adapter development.

It exposes:

```python
sink.observations
sink.by_name("scheduler.cycle.completed")
sink.count("execution.attempt.completed")
```

## Scheduler cycle observation

Every completed `run_pending()` cycle emits:

```text
scheduler.cycle.completed
```

with aggregate attributes:

```text
materialized_requests
executions
succeeded
failed
retry_scheduled
schedule_conflicts
recovery_limit_schedules
admissions
queued
dropped
admission_lock_denied
claim_denied
materialization_denied
errors
shutdown_requested
```

These are aggregate counts rather than Schedule or Execution IDs.

This avoids forcing high-cardinality dimensions into metrics backends.

## Attempt observation

Every completed local Attempt emits:

```text
execution.attempt.completed
```

with:

```text
attempt_number
state
succeeded
retry_scheduled
failure_category
```

Identifiers are deliberately omitted from the default observation.

Correlation-rich logging or tracing adapters may add their own contextual policies later without changing the base scheduler contract.

## Runtime observations

The continuous loop emits:

```text
runtime.cycle.completed
runtime.wait.planned
```

with:

```text
cycle_number
delay_seconds
```

This makes runtime progress and adaptive sleep decisions externally visible.

## Public API

```python
from pyschedulekit import (
    InMemoryObservationSink,
    Scheduler,
)

sink = InMemoryObservationSink()

scheduler = Scheduler(
    observation_sink=sink,
)
```

Custom adapters only need to implement `ObservationSink`.

## Metrics mapping

A Prometheus-style adapter can map observations approximately as:

```text
scheduler.cycle.completed
  → pyschedulekit_scheduler_cycles_total
  → materialized/execution outcome counters

execution.attempt.completed
  → pyschedulekit_execution_attempts_total{state=...}

runtime.cycle.completed
  → pyschedulekit_runtime_cycles_total

runtime.wait.planned
  → pyschedulekit_runtime_wait_seconds
```

The exact metric naming is adapter policy and is not hard-coded in the core.

## Cardinality policy

Core observations do not emit by default:

```text
schedule_id
execution_id
request_id
attempt_id
target reference
exception message
arbitrary payloads
```

Reasons:

- metric cardinality safety;
- privacy;
- bounded memory/storage use;
- backend portability.

Detailed correlation can be layered through specialized tracing/logging adapters in a future lot.

## Time semantics

Observation timestamps reuse existing explicit scheduler time:

- `scheduler.cycle.completed` uses `evaluation_now`;
- `execution.attempt.completed` uses the Attempt completion timestamp;
- runtime observations reuse the completed cycle's evaluation snapshot.

LOT-30 introduces no hidden wall-clock read into the domain model.

## Safety properties

1. scheduler behavior is unchanged when no sink is configured;
2. telemetry sink exceptions never fail scheduler operations;
3. observations are immutable;
4. observation attribute ordering is deterministic;
5. cycle metrics are aggregated and bounded;
6. default observations avoid entity identifiers;
7. runtime instrumentation is thread-safe through sink adapters;
8. no third-party observability dependency is mandatory.

## Qualification

LOT-30 qualifies:

- Observation validation;
- deterministic attribute normalization;
- in-memory sink querying;
- sink-failure isolation;
- successful Attempt observation;
- successful scheduler-cycle observation;
- no-op scheduler-cycle observation;
- continuous runtime cycle observation;
- continuous runtime wait-plan observation;
- public Scheduler wiring.

## Production maturity roadmap

```text
LOT-30  Observability            ✅
LOT-31  Operational API          ✅
LOT-32  Retention / Cleanup     ⏭ NEXT
LOT-33  Additional Executors     ⬜
LOT-34  Public API Hardening     ⬜
```

## Next

`LOT-32 — Retention / Cleanup`
