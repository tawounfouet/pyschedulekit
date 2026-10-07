# LOT-20 — Graceful Shutdown

## Goal

Give the continuous runtime an explicit shutdown contract that distinguishes:

```text
stop loop
≠
stop starting new work
≠
wait for active work
≠
cancel active work
≠
force-kill arbitrary code
```

## Public API

Non-blocking loop stop remains available:

```python
scheduler.stop()
```

Graceful shutdown is explicit:

```python
result = scheduler.shutdown(
    mode=ShutdownMode.WAIT,
    timeout=Duration.seconds(30),
)
```

or:

```python
result = scheduler.shutdown(
    mode=ShutdownMode.CANCEL,
    timeout=Duration.seconds(30),
)
```

## Shutdown modes

### WAIT

```text
request shutdown
    ↓
close new-work gate
    ↓
stop runtime loop
    ↓
let active Attempt finish
    ↓
do not start another Attempt
    ↓
return when runtime is stopped
```

WAIT never asks the active workload to cancel.

### CANCEL

```text
request shutdown
    ↓
close new-work gate
    ↓
stop runtime loop
    ↓
signal active CancellationToken
    ↓
persist cancellation intent when RUNNING
    ↓
wait for active Attempt to terminate
    ↓
return when runtime is stopped
```

CANCEL remains cooperative. Python threads are not force-killed.

## Atomic new-work gate

LOT-20 introduces a process-local `ShutdownCoordinator`.

The same lock protects:

- shutdown request state;
- admission of new ExecutionRunner work;
- the set of active Execution IDs.

The runner uses:

```text
try_enter(execution_id)
```

before starting an Attempt.

After shutdown is requested, new entries are refused atomically.

This closes the race between:

```text
run_pending checks shutdown
        ↕
ExecutionRunner starts work
```

## Mid-cycle behavior

A single `run_pending()` cycle may have multiple runnable Executions.

LOT-20 checks the shutdown barrier:

- before the cycle begins;
- before each admission;
- before each Execution;
- again atomically at ExecutionRunner entry.

Therefore shutdown during the first active Attempt prevents the second Attempt from starting when control returns to the loop.

## Active execution tracking

The coordinator keeps only process-local currently active Execution IDs.

```text
try_enter(id)
    ↓
active set contains id
    ↓
executor invocation
    ↓
leave(id)
```

This gives graceful shutdown a deterministic drain primitive without polling persistence.

## Timeout semantics

A shutdown timeout applies to the whole shutdown operation.

```python
result = scheduler.shutdown(
    timeout=Duration.seconds(5),
)
```

If the deadline expires before active work drains or before the runtime fully stops:

```text
result.completed == False
result.timed_out == True
result.active_execution_ids
```

The scheduler does not claim successful shutdown while work is still active.

## ShutdownResult

```text
mode
completed
timed_out
active_execution_ids
```

A successful graceful shutdown has:

```text
completed = True
timed_out = False
active_execution_ids = ()
```

## Relationship with cancellation

Shutdown CANCEL reuses LOT-17 cooperative cancellation.

For an already RUNNING Execution:

```text
cancellation_requested_at
+
CancellationToken.cancel()
```

For a runner reservation that has entered the shutdown coordinator but has not yet persisted RUNNING state, the process-local token is still signalled. When the Attempt starts, it observes cancellation immediately.

## Relationship with retry

Shutdown does not create retry behavior.

If an Attempt is cooperatively cancelled:

```text
Attempt CANCELLED
→ Execution CANCELLED
→ no retry
```

WAIT allows the normal Attempt result and retry policy to complete. However the shutdown gate prevents a retry Attempt from starting during the same drain.

Durable RETRY_WAIT state remains available for a later runtime restart.

## Restart behavior

`run_forever()` explicitly resets shutdown coordination before starting.

Reset is refused while an Execution is still active.

Therefore a timed-out shutdown cannot be bypassed by immediately restarting the runtime while the old active workload is still draining.

## stop() vs shutdown()

`stop()` remains intentionally lightweight:

```text
stop()
→ request loop termination
→ non-blocking
```

`shutdown()` is the stronger lifecycle operation:

```text
shutdown()
→ close new-work gate
→ stop loop
→ optional cooperative cancellation
→ wait for drain
→ wait for runtime return
→ structured result
```

## Safety properties

1. new Attempts cannot enter after shutdown is requested;
2. the gate and active set are coordinated atomically;
3. a mid-cycle shutdown prevents later work in that cycle;
4. WAIT never cancels active work;
5. CANCEL reuses cooperative cancellation;
6. no hard-kill guarantee is implied;
7. shutdown timeout is explicit;
8. timeout reports remaining active Execution IDs;
9. runtime stop and active drain are both awaited;
10. restart is refused while old active work remains.

## Qualification

LOT-20 qualifies:

- shutdown request blocks new Execution entry;
- active Execution tracking and drain;
- deterministic active-ID snapshot;
- WAIT lets the current Attempt finish;
- WAIT prevents a second due Attempt from starting;
- CANCEL terminates a cooperative target;
- CANCEL persists explicit CANCELLED lifecycle state;
- shutdown timeout reports still-active work;
- runtime thread is fully stopped before successful return.

## Non-goals

LOT-20 does not implement:

- SIGTERM/SIGINT handlers;
- process termination;
- force-killing threads;
- distributed shutdown coordination;
- worker fencing;
- SQL-backed runtime ownership;
- crash recovery.

## Next

`LOT-21 — SQL Persistence Foundations`
