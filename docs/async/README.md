# 0.2.x — Async Python Executor

PyScheduleKit now supports trusted `async def` Python workloads **without changing the
synchronous Scheduler, domain model, persistence ports or Executor protocol**.

## Architectural boundary

The existing control plane remains synchronous:

```text
Scheduler.run_pending()
        ↓
ExecutionRunner
        ↓
Executor.execute()            # synchronous port
        ↓
RoutingExecutor
        ↓
python_async → AsyncioExecutor
        ↓
dedicated worker thread
        ↓
asyncio.run(coroutine)
```

This deliberately follows the target-architecture rule:

> do not mix synchronous and asynchronous methods in the same Protocol.

Async support is therefore an execution-adapter capability, not a second scheduling domain.

## Public surface

```python
from pyschedulekit import (
    AsyncioExecutor,
    AsyncPythonTargetRegistry,
    Scheduler,
    TargetRef,
)
```

### Automatic registration

```python
async def refresh_cache() -> None: ...


scheduler = Scheduler()
scheduler.add_schedule(
    target=refresh_cache,
    trigger=...,
)
```

`Scheduler.add_schedule()` detects a coroutine function and stores a declarative
`TargetRef(kind="python_async", ...)`.

### Explicit registration

```python
target = scheduler.register_async_target(
    "jobs:refresh-cache",
    refresh_cache,
)

assert target == TargetRef.async_python("jobs:refresh-cache")
```

As with synchronous Python targets, executable callables remain process-local trusted
configuration. Durable persistence stores only the declarative target reference.

## Registry contract

`AsyncPythonTargetRegistry` accepts only explicit `async def` functions.

Required parameters are restricted to:

```text
cancellation_token
fencing_token
```

Everything else must be optional or variadic.

The registry also supports exact-target unregister compensation so a failed
`Scheduler.add_schedule()` cannot leave orphan executable configuration.

## Event-loop model

The first async adapter uses one dedicated worker thread per execution.

Inside that worker:

```python
asyncio.run(...)
```

owns a fresh event loop.

This has two important consequences:

1. callers may invoke the synchronous Scheduler from a thread that already has a running
   asyncio event loop;
2. PyScheduleKit does not attempt nested `asyncio.run()` calls on the caller thread.

This is intentionally simple and safe for the first adapter. A shared long-lived async
runtime/pool is a separate future optimization.

## Timeout

A configured schedule timeout becomes:

```python
await asyncio.wait_for(target(), timeout=...)
```

Timeout cancellation is normalized to the existing framework outcome:

```text
FailureCategory.TIMEOUT
code = execution.timeout
```

The retry lifecycle remains owned by `ExecutionRunner` / `RetryEvaluator`; the async
executor never retries by itself.

## Cancellation

Cancellation remains cooperative.

Before invocation, an already-cancelled execution never runs the target.

An async target may accept:

```python
async def target(cancellation_token):
    cancellation_token.raise_if_cancelled()
    ...
```

`ExecutionCancelledError` and `asyncio.CancelledError` normalize to:

```text
FailureCategory.CANCELLED
code = execution.cancelled
```

A target that never checks its cancellation token cannot be forcefully stopped merely by
requesting cancellation. Timeout remains the bounded escape path.

## Fencing

Distributed claim generation crosses the same executor boundary:

```python
async def target(fencing_token: int) -> None: ...
```

The value is injected only when the callable declares the parameter.

This preserves the same stale-worker protection model as synchronous local and HTTP
execution.

## Failure handling

An application exception is normalized without persisting its raw message:

```text
category = UNKNOWN
code = python_async.exception
details = exception_type only
```

Secrets accidentally embedded in an exception message therefore do not become persisted
scheduler state.

## Retry

Async workloads use the existing durable retry policy unchanged:

```text
async target raises
      ↓
ExecutorOutcome(UNKNOWN)
      ↓
RetryEvaluator
      ↓
RETRY_WAIT
      ↓
backoff deadline
      ↓
next async Attempt
```

No new persistence schema is required.

## Scope

This milestone provides:

- trusted `async def` target registration;
- automatic async callable detection;
- async timeout;
- cooperative cancellation;
- fencing token injection;
- retry integration;
- Scheduler E2E qualification.

It does **not** provide:

- an `AsyncScheduler`;
- async persistence / async PostgreSQL;
- an async `Executor` Protocol;
- concurrent coroutine multiplexing on one shared loop;
- automatic event-loop ownership by the application;
- CPU-bound execution acceleration.

Those concerns should remain separate until a concrete need justifies them.

## Next

After the Async Python Executor is qualified, the next 0.2.x milestone is the
**executor plugin registry** so third-party executor families can be discovered/configured
without expanding Scheduler-specific branches.

---

**Status:** 0.2.x — Async Python Executor.
