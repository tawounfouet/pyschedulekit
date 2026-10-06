# LOT-10 — Local Executor

## Goal

Execute the first real Python workload while preserving the domain, security, and transaction boundaries established by the previous lots.

The central chain becomes:

```text
Execution QUEUED
      │
      ▼
resolve TargetRef
      │
      ▼
Attempt RUNNING committed
      │
      ▼
invoke callable outside transaction
      │
      ├── normal return
      │      ▼
      │   SUCCESS
      │
      └── Exception
             ▼
          Failure
             ▼
           FAILED
```

## Security decision: registry only

LOT-10 does not interpret:

```text
TargetRef.python("package.module:function")
```

as authority to import arbitrary Python code.

Instead, the local executor uses an explicit trusted registry:

```python
registry.register("refresh", refresh)
```

and the Schedule uses:

```python
TargetRef.python("refresh")
```

The reference is an opaque alias.

This implements the security principle:

> Configuration is data, not executable authority.

## No arbitrary import

The local executor does not use:

- importlib from persisted target data;
- eval;
- exec;
- pickle;
- dynamic module/class loading.

Unknown aliases fail closed with `TargetResolutionError`.

Unsupported target kinds fail with `UnsupportedTargetError`.

## PythonTargetRegistry

The registry accepts synchronous zero-required-argument callables.

Registration rejects:

- empty references;
- duplicate references;
- async functions;
- callables with required arguments;
- callables whose signature cannot be inspected.

Optional arguments remain allowed because the callable can still be invoked with zero arguments.

## Sync-only V1

The first LocalExecutor is synchronous.

Native async callables are rejected during registration.

If a synchronous wrapper dynamically returns an awaitable, the invocation is normalized into a permanent Failure:

```text
python.async_result_not_supported
```

Async execution belongs to a future explicit executor rather than implicit event-loop behavior.

## Executor port

LOT-10 introduces:

- `Executor`;
- `PreparedTarget`;
- `ExecutorOutcome`;
- `ExecutorError`;
- `TargetResolutionError`;
- `UnsupportedTargetError`.

The port deliberately separates:

```text
prepare(target)
```

from:

```text
execute(prepared)
```

This is essential to the error model.

## Resolution before Attempt

Target resolution is a control-plane operation.

Therefore:

```text
resolve target
↓
success
↓
start Attempt
```

not:

```text
start Attempt
↓
resolution fails
↓
fake workload Failure
```

If an alias is missing or unsupported:

- Execution remains QUEUED;
- attempt_count remains zero;
- no Attempt row exists.

## Attempt committed before side effect

ExecutionRunner performs:

```text
prepare target
      │
      ▼
ExecutionService.start_attempt()
      │
      ▼
COMMIT
Execution = RUNNING
Attempt = RUNNING
      │
      ▼
invoke callable
```

Therefore the external side effect never begins before durable state says that an Attempt is running.

This creates the recovery evidence required after a process crash.

## No transaction around workload execution

The callable is invoked after `start_attempt()` has committed and returned.

No UnitOfWork remains open across arbitrary user code.

This prevents:

- long database transactions;
- locks held during user work;
- rollback pretending an external side effect never happened.

## Successful callable

A normal Python return produces:

```text
ExecutorOutcome(failure=None)
```

The callable's return value is currently ignored.

PyScheduleKit V1 does not infer scheduling semantics from arbitrary business return values.

The runner then persists:

```text
Attempt → SUCCESS
Execution → SUCCESS
```

## Python Exception normalization

LocalExecutor catches:

```python
Exception
```

not:

```python
BaseException
```

A normal target exception becomes:

```text
FailureCategory.UNKNOWN
code = python.exception
retryable_hint = None
```

The persisted Failure does not include the raw exception message.

It records only safe structured metadata such as:

```text
exception_type = RuntimeError
```

This reduces accidental secret leakage.

## Why UNKNOWN

LOT-10 cannot universally infer that:

```text
ConnectionError
→ retryable
```

or:

```text
ValueError
→ permanent
```

without application-specific classification rules.

Therefore arbitrary callable exceptions default to:

```text
UNKNOWN
```

and future RetryPolicy must fail closed unless an explicit classifier provides stronger semantics.

## BaseException behavior

`SystemExit`, `KeyboardInterrupt`, and similar BaseException subclasses are not converted into workload Failures.

If a process-level interruption occurs after the Attempt started:

```text
Execution = RUNNING
Attempt = RUNNING
```

remain durable.

This is intentional.

A future recovery/reconciliation lot will decide how stale running Attempts are handled.

## ExecutionRunner

LOT-10 adds an application-level runner:

```text
ExecutionRunner
├── UnitOfWorkFactory
├── ExecutionService
├── Executor
└── Clock
```

The runner orchestrates one Execution at a time.

It does not discover queued work globally yet.

## Explicit Clock

Time remains explicit through the injected Clock port.

The runner captures:

```text
started_at
completed_at
```

and LocalExecutor uses the same explicit Clock to timestamp normalized Failures.

No direct `datetime.now()` is introduced.

## Transaction boundaries

The successful path has three phases:

### Phase 1 — read and prepare

```text
load Execution target
close read transaction
prepare TargetRef
```

### Phase 2 — mark running

```text
Execution QUEUED
Attempt created
single commit
```

### Phase 3 — effect and completion

```text
invoke callable
(no transaction)

then

Attempt terminal
Execution terminal
single commit
```

This boundary is fundamental for all future executors.

## Crash window

A crash may happen after the callable produces an external side effect but before the terminal result commit.

LOT-10 does not pretend to provide exactly-once side effects.

The durable state may remain:

```text
Execution RUNNING
Attempt RUNNING
```

even though the target partially or fully executed.

Future recovery therefore requires:

- stale-running detection;
- idempotency keys;
- reconciliation;
- explicit retry policy.

This is precisely why `IdempotencyKey` was introduced in LOT-09.

## No implicit retry

When LocalExecutor returns a Failure, ExecutionRunner calls:

```text
fail_attempt(..., retry_at=None)
```

Therefore:

```text
Attempt FAILED
Execution FAILED
```

LOT-10 does not inspect `retryable_hint` and does not automatically enter `RETRY_WAIT`.

Retry decisions remain the responsibility of the dedicated RetryPolicy lot.

## Qualification scenarios

LOT-10 proves:

- explicit registry resolution;
- duplicate registry keys rejected;
- empty keys rejected;
- required-argument callables rejected;
- async functions rejected;
- unknown alias rejected;
- unsupported target kind rejected;
- registered callable invoked exactly as a local target;
- arbitrary Exception normalized to Failure;
- raw exception message not persisted;
- BaseException not swallowed;
- dynamically returned awaitable rejected;
- callable return value ignored;
- successful callable completes Attempt and Execution;
- target exception fails Attempt and Execution;
- resolution failure creates no Attempt;
- unsupported kind creates no Attempt;
- RUNNING state is durable before the callable executes;
- process-like crash leaves RUNNING state for recovery;
- local executor applies no implicit retry.

## Intentionally deferred

LOT-10 does not implement:

- HTTP executor;
- workflow executor;
- subprocess/shell executor;
- async executor;
- automatic retry;
- timeout enforcement;
- worker pool;
- queue claiming;
- continuous runtime;
- stale-running recovery.

## Architecture progression

```text
SchedulerEngine
      │
      ▼
ExecutionRequest
      │
      ▼
ExecutionService.dispatch()
      │
      ▼
Execution QUEUED
      │
      ▼
ExecutionRunner
      │
      ├── prepare LocalExecutor target
      ├── persist RUNNING Attempt
      ├── invoke callable
      └── persist terminal result

NEXT:
run_pending()
```

## Exit criteria

LOT-10 is complete when:

- target resolution is explicit and allowlisted through registration;
- resolution errors happen before Attempt creation;
- user code runs outside UnitOfWork transactions;
- RUNNING state is committed before side effects;
- target Exceptions become normalized Failures;
- BaseException is not swallowed;
- successful and failed executions persist terminal state;
- no retry policy is hidden inside the executor;
- all quality gates are green.

## Next

`LOT-11 — run_pending() End-to-End Slice`
