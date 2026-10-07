# LOT-17 — Cancellation Refinements

## Goal

Turn the cancellation states introduced by the execution lifecycle into an explicit control-plane contract.

Cancellation is modeled in three layers:

```text
Cancellation request
        ↓
durable Execution state
        +
process-local cancellation token
        ↓
cooperative workload observation
        ↓
Attempt CANCELLED
        ↓
Execution CANCELLED
```

## Core semantics

Cancellation behavior depends on the current Execution state.

```text
QUEUED
  └── cancel immediately → CANCELLED

RETRY_WAIT
  └── cancel immediately → CANCELLED

RUNNING
  └── persist cancellation_requested_at
      + signal CancellationToken
      + wait for cooperative completion
      → Attempt CANCELLED
      → Execution CANCELLED

terminal state
  └── cancellation request is idempotent
```

A cancelled Attempt is never eligible for Retry.

## Public API

Cancellation is requested through:

```python
scheduler.cancel_execution(execution_id)
```

The method accepts either an `ExecutionId` or its string value.

For idle work, the returned Execution is already terminal.

For running work, the returned Execution records a durable cancellation request while the cooperative signal is sent to the local worker.

## Cooperative targets

A regular target remains unchanged:

```python
def job() -> None:
    ...
```

A cooperative target declares exactly one required argument named `cancellation_token`:

```python
def job(cancellation_token: CancellationToken) -> None:
    while work_remains():
        cancellation_token.raise_if_cancelled()
        do_one_unit()
```

The local registry detects this explicit signature and injects the token.

No cancellation parameter is injected into legacy zero-argument callables.

## CancellationToken

The public token exposes:

```text
is_cancelled
raise_if_cancelled()
```

`raise_if_cancelled()` raises `ExecutionCancelledError`.

The LocalExecutor catches that control-flow exception and normalizes it to:

```text
FailureCategory.CANCELLED
code = execution.cancelled
retryable_hint = False
```

## Durable request state

A running Execution records:

```text
cancellation_requested_at
```

This metadata is persisted by the in-memory repository and survives independent UnitOfWork boundaries.

Repeated requests are idempotent and preserve the original request timestamp.

## Retry interaction

Cancellation always wins over retry.

```text
Attempt RUNNING
    ↓
Cancellation requested
    ↓
Attempt CANCELLED
    ↓
Execution CANCELLED
    ↓
no RetryEvaluator decision
no RETRY_WAIT
```

A cancellation requested while an Execution is already in `RETRY_WAIT` removes it from future runnable work immediately.

## Timeout interaction

Timeout and cancellation are different outcomes.

```text
TIMEOUT
  → retryable by default

CANCELLED
  → explicitly non-retryable
```

A cooperative cancellation observed before timeout yields CANCELLED.

If a non-cooperative callable ignores cancellation, PyScheduleKit cannot force-kill the Python thread. The configured timeout may still return scheduler control later.

## Local-runtime limitation

Python does not provide safe forced termination of arbitrary threads.

LOT-17 therefore guarantees:

- durable cancellation intent;
- immediate process-local signalling;
- cooperative cancellation for token-aware workloads;
- cancellation normalization after a non-cooperative callable eventually returns.

It does not guarantee immediate physical termination of arbitrary code.

Hard termination requires process isolation, worker fencing, or an executor with stronger cancellation semantics.

## Concurrency interaction

QUEUED or RETRY_WAIT cancellation makes the Execution terminal immediately and therefore releases LOT-14 concurrency capacity.

RUNNING cancellation releases capacity when the Attempt reaches terminal CANCELLED state.

## Safety properties

1. cancellation requests are explicit and durable;
2. idle Executions cancel immediately;
3. running Executions record cancellation before signalling workers;
4. repeated requests are idempotent;
5. cooperative targets receive a read-only token;
6. legacy targets remain backward compatible;
7. CANCELLED failures are non-retryable;
8. RETRY_WAIT cancellation prevents later Attempts;
9. token state is process-local and thread-safe;
10. no hard-kill guarantee is implied.

## Qualification

LOT-17 qualifies:

- immediate queued cancellation;
- durable running cancellation request;
- request idempotence;
- cooperative target cancellation;
- AttemptState.CANCELLED persistence;
- no retry after cancellation;
- RETRY_WAIT cancellation;
- public Scheduler cancellation during a running cycle;
- public cancellation token injection.

## Non-goals

LOT-17 does not implement:

- process termination;
- distributed cancellation signalling;
- persistent cancellation-token transport;
- leases or fencing;
- remote executor cancellation APIs;
- crash reconciliation.

## Next

`LOT-18 — Continuous Scheduler Loop`
