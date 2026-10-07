# LOT-16 — Execution Timeout

## Goal

Make the timeout field introduced by the execution lifecycle operational.

```text
Attempt starts
    ↓
Executor invokes workload
    ↓
deadline reached?
    ├── no  → normal outcome
    └── yes → TIMEOUT Failure
                 ↓
          Attempt TIMED_OUT
                 ↓
          RetryEvaluator
          ├── retry → RETRY_WAIT
          └── stop  → Execution TIMED_OUT
```

## Public configuration

```python
scheduler.add_schedule(
    target=my_job,
    trigger=my_trigger,
    timeout=Duration.seconds(30),
)
```

A timeout is optional. When omitted, historical synchronous behavior is preserved. Configured durations must be strictly greater than zero.

## Durable timeout snapshot

```text
ScheduleDefinition.timeout
        ↓
ExecutionRequest.timeout
        ↓
ExecutionPolicySnapshot.timeout
        ↓
ExecutionRunner
```

A later Schedule change cannot retroactively alter the timeout of already materialized execution intent.

## Attempt semantics

Timeout is evaluated per Attempt. Every retry receives a fresh timeout window.

Completion at or after the configured deadline is treated as timed out:

```text
elapsed < timeout  → normal outcome
elapsed >= timeout → TIMED_OUT
```

## Runtime enforcement

`LocalExecutor.execute()` accepts an optional timeout. Without one, invocation remains synchronous. With one, the callable runs on a daemon worker thread while the scheduler waits only up to the configured duration.

## Local-runtime limitation

Python cannot safely force-kill an arbitrary running thread. LOT-16 therefore bounds how long the scheduler waits; it does not claim guaranteed workload termination.

After the deadline:

- the Attempt is durably marked `TIMED_OUT`;
- the scheduler regains control;
- RetryPolicy may schedule another Attempt;
- the expired callable may still finish in its daemon thread.

This matters for irreversible external side effects. Cooperative cancellation, isolation and fencing belong to later execution work.

## Failure normalization

Local timeout produces:

```text
FailureCategory.TIMEOUT
code = execution.timeout
retryable_hint = True
```

The lifecycle is persisted through `ExecutionService.timeout_attempt()` rather than the generic failure path.

## Retry interaction

`TIMEOUT` is retryable by default under LOT-15. Timeout enforcement never retries implicitly inside the executor; `RetryEvaluator` remains the sole owner of retry decisions.

```text
Attempt #1 → TIMED_OUT
             ↓
         RETRY_WAIT
             ↓
Attempt #2 → fresh timeout window
```

## Safety properties

1. timeout is optional and durable;
2. zero timeout is rejected;
3. timeout applies per Attempt;
4. expiration produces `FailureCategory.TIMEOUT`;
5. timed-out Attempts use `AttemptState.TIMED_OUT`;
6. exhausted retries terminate the Execution as `TIMED_OUT`;
7. RetryPolicy remains responsible for retry decisions;
8. no-timeout behavior remains backward compatible;
9. scheduler control returns at the deadline;
10. hard thread termination is explicitly not guaranteed.

## Qualification

LOT-16 qualifies positive and zero timeout configuration, durable snapshots, deterministic elapsed-clock timeout, explicit TIMED_OUT persistence, timeout-to-retry-to-success, watchdog return before a blocking callable finishes, and public Scheduler behavior.

## Non-goals

- forceful thread termination;
- cooperative cancellation tokens;
- cancellation API refinements;
- process isolation;
- distributed timeout enforcement;
- leases/fencing;
- crash reconciliation.

## Next

`LOT-17 — Cancellation Refinements`
