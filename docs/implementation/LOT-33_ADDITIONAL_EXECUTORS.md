# LOT-33 — Additional Executors

## Goal

Prove that PyScheduleKit's execution lifecycle is independent from one concrete workload transport.

Before LOT-33 the architecture exposed an `Executor` port, but the public `Scheduler` still instantiated `LocalExecutor` directly. LOT-33 removes that final hard wiring.

The target architecture is:

```text
Schedule / Execution
        │
        ▼
TargetRef(kind, reference)
        │
        ▼
RoutingExecutor
        │
        ├── python → LocalExecutor
        ├── http   → HttpExecutor
        └── custom → application-provided Executor
```

Scheduling, durability, retries, cancellation, leases, fencing, recovery, reconciliation and observability remain independent from the concrete executor.

## Executor contract

The existing port remains intentionally small:

```python
class Executor(Protocol):
    def prepare(self, target: TargetRef) -> PreparedTarget: ...

    def execute(
        self,
        prepared: PreparedTarget,
        *,
        timeout: Duration | None = None,
        cancellation_token: CancellationToken | None = None,
        fencing_token: int | None = None,
        idempotency_key: str | None = None,
    ) -> ExecutorOutcome: ...
```

LOT-33 adds `idempotency_key` to the execution metadata crossing this boundary.

## Why target preparation remains separate

`prepare()` runs before an Attempt becomes RUNNING.

Therefore unresolved or unsupported targets fail as control-plane errors rather than creating a false workload Attempt.

```text
TargetRef
   ↓
prepare() fails
   ↓
NO Attempt started
```

This invariant is preserved for every executor kind.

## RoutingExecutor

`RoutingExecutor` maps one target kind to one concrete adapter:

```python
RoutingExecutor(
    {
        "python": local_executor,
        "http": http_executor,
        "workflow": custom_workflow_executor,
    }
)
```

The router stores the executor selected at preparation time inside `RoutedPreparedTarget`. Execution therefore cannot be accidentally re-routed after an Attempt starts.

The router also verifies that a concrete executor did not prepare a different `TargetRef` than the one requested.

## Default Scheduler composition

`Scheduler` now composes:

```text
PythonTargetRegistry → LocalExecutor ─┐
                                     ├→ RoutingExecutor → ExecutionRunner
HttpTargetRegistry   → HttpExecutor  ─┘
```

Applications may extend or replace kinds:

```python
scheduler = Scheduler(
    executors={"workflow": workflow_executor},
)
```

The scheduling engine requires no workflow-specific branch.

## HTTP targets are opaque references

`TargetRef.http()` does not persist raw request credentials or arbitrary request bodies as scheduler configuration.

Instead:

```text
TargetRef.http("billing-webhook")
        ↓
HttpTargetRegistry
        ↓
HttpRequestSpec(
    url="https://service.example/hooks/billing",
    method=POST,
    headers=...,
    body=...,
)
```

This follows the same trust model as `PythonTargetRegistry`: durable scheduling state stores an opaque reference, while process-local application configuration resolves it.

## HttpRequestSpec validation

Built-in validation rejects:

- non-HTTP(S) URLs;
- URLs embedding username/password credentials;
- empty or duplicated header names;
- CR/LF header injection;
- user-defined scheduler-reserved execution headers.

Reserved headers are:

```text
Idempotency-Key
X-PyScheduleKit-Fencing-Token
```

## HTTP outcome semantics

HTTP responses are normalized into existing `Failure` categories.

```text
2xx             → SUCCESS

400/401/403/404 → PERMANENT
other 4xx       → PERMANENT

408             → TRANSIENT
425             → TRANSIENT
429             → TRANSIENT
5xx             → TRANSIENT

socket timeout  → TIMEOUT
transport error → TRANSIENT
cancelled       → CANCELLED
```

Failure details expose the status code when relevant, but never persist response bodies or raw network exception text.

## Idempotency propagation

Every `Execution` already has a durable deterministic `IdempotencyKey` preserved across Attempts.

LOT-33 now propagates it:

```text
Execution.idempotency_key
        ↓
ExecutionRunner
        ↓
Executor.execute(idempotency_key=...)
        ↓
HttpExecutor
        ↓
Idempotency-Key: <stable value>
```

A retry therefore presents the same idempotency key to the remote endpoint.

## Fencing propagation

Distributed execution ownership already uses a monotonically increasing claim generation.

For HTTP targets:

```text
ExecutionClaim.generation
        ↓
Executor.execute(fencing_token=...)
        ↓
X-PyScheduleKit-Fencing-Token: <generation>
```

A remote service can use this value to reject stale worker generations if it supports fenced writes.

## Cancellation semantics

The HTTP adapter checks cooperative cancellation before I/O and again after the HTTP call returns.

The standard-library synchronous HTTP stack does not provide a portable asynchronous abort primitive for an already-blocking request. Runtime timeout remains the bounded escape mechanism for in-flight blocking I/O.

LOT-33 does not claim stronger cancellation guarantees than the underlying adapter can provide.

## Retry integration

`HttpExecutor` does not perform retries itself.

```text
HTTP 503
   ↓
ExecutorOutcome(TRANSIENT)
   ↓
ExecutionRunner
   ↓
RetryEvaluator
   ↓
RETRY_WAIT / terminal FAILED
```

Retry policy remains a domain/application concern, preserving the architecture established in LOT-15.

## Observability

`execution.attempt.completed` now includes:

```text
target_kind = python | http | workflow | ...
```

This makes executor-family metrics possible without introducing executor-specific metric systems.

## No new persistence schema

LOT-33 requires no SQLite schema migration.

`TargetRef.kind` and `TargetRef.reference` were already durable first-class fields, and `Execution.idempotency_key` already existed before this lot.

LOT-33 only activates those existing abstractions across more execution adapters.

## Non-goals

LOT-33 does not implement:

- Celery or RQ;
- Kubernetes Jobs;
- Docker execution;
- SSH execution;
- a workflow engine;
- browser automation;
- arbitrary shell-command execution;
- distributed HTTP response storage;
- automatic secret management;
- durable executor registry configuration.

These can be adapters over the same port when justified.

## Safety invariants

1. target resolution occurs before Attempt start;
2. unsupported kinds never silently fall back to another executor;
3. routing is determined by explicit `TargetRef.kind`;
4. executor adapters do not own retry policy;
5. remote HTTP failures are normalized without raw response-body persistence;
6. retries preserve one Execution idempotency key;
7. claim generation crosses the executor boundary as fencing metadata;
8. custom executors use the same lifecycle as built-ins;
9. LocalExecutor behavior remains backward compatible;
10. LOT-33 adds no external runtime dependency.

## Qualification

LOT-33 qualifies:

- routing by target kind;
- unsupported-kind rejection;
- prepared-target identity preservation;
- HTTP target validation;
- HTTP success;
- permanent 4xx classification;
- retryable 408/425/429/5xx classification;
- network failure classification;
- timeout classification;
- pre-I/O cancellation;
- idempotency header propagation;
- fencing header propagation;
- HTTP retry through existing RetryPolicy;
- custom workflow executor injection;
- `target_kind` observability;
- Python 3.11/3.12/3.13 compatibility.

## Production maturity roadmap

```text
LOT-30  Observability            ✅
LOT-31  Operational API          ✅
LOT-32  Retention / Cleanup      ✅
LOT-33  Additional Executors     ✅
LOT-34  Public API Hardening    ⏭ NEXT
```

## Next

`LOT-34 — Public API Hardening`
