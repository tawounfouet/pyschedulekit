# LOT-15 — Retry Policy Foundations

## Goal

Introduce explicit retry semantics without hiding retries inside the executor.

The core flow is:

```text
Attempt fails
    ↓
RetryEvaluator
    ↓
RetryDecision
    ├── STOP  → terminal Execution
    └── RETRY → RETRY_WAIT
                   ↓
             next_attempt_at
                   ↓
            later run_pending()
                   ↓
              next Attempt
```

## Core rules

1. `max_attempts` includes the initial Attempt.
2. A retry keeps the same logical `ExecutionId`.
3. Every retry creates the next numbered `Attempt`.
4. Backoff is pure data and never implemented with `sleep()`.
5. Retry policy is snapshotted when durable scheduling intent is materialized.
6. `Failure.retryable_hint` overrides default category classification.
7. By default, TRANSIENT, TIMEOUT, and UNKNOWN failures are retryable.
8. PERMANENT and CANCELLED failures are not retryable by default.
9. One `run_pending()` cycle performs at most one Attempt for a given Execution.
10. RETRY_WAIT remains a non-terminal admitted Execution and therefore keeps LOT-14 capacity reserved.

## RetryPolicy

```python
RetryPolicy(
    max_attempts=4,
    backoff=ExponentialBackoff(
        initial_delay=Duration.seconds(1),
        multiplier=2,
        max_delay=Duration.seconds(30),
    ),
)
```

`max_attempts=1` is the neutral policy and preserves pre-LOT-15 behavior.

## Backoff strategies

Built-in strategies:

```text
NoBackoff
FixedBackoff
ExponentialBackoff
```

For exponential backoff:

```text
initial_delay = 1s
multiplier    = 2

Attempt #1 failed → 1s
Attempt #2 failed → 2s
Attempt #3 failed → 4s
Attempt #4 failed → 8s
```

An optional `max_delay` caps the calculated delay.

## Failure classification

Retry decisions consume normalized `Failure` values rather than raw Python exceptions.

Priority:

```text
retryable_hint is True  → retry eligible
retryable_hint is False → stop
retryable_hint is None  → classify by FailureCategory
```

The default retryable categories are:

```text
TRANSIENT
TIMEOUT
UNKNOWN
```

This keeps retry configuration declarative and persistence-friendly.

## Durable policy snapshots

The policy is captured through:

```text
ScheduleDefinition.retry
        ↓
ExecutionRequest.retry_policy
        ↓
ExecutionPolicySnapshot.retry
```

A later Schedule reschedule therefore cannot retroactively change retry behavior of an already-materialized execution intent.

## Execution lifecycle

LOT-09 already introduced RETRY_WAIT and `next_attempt_at`; LOT-15 makes those states operational.

```text
QUEUED
  ↓
RUNNING
  ↓
Attempt FAILED
  ↓
RetryEvaluator
  ├── STOP  → FAILED
  └── RETRY → RETRY_WAIT
                  ↓
          next_attempt_at due
                  ↓
               RUNNING
```

## Non-blocking runtime

Backoff never calls `sleep()`.

Instead:

```text
completed_at + delay
        ↓
next_attempt_at
```

The in-memory repository exposes due retry-wait executions through `list_runnable(now=...)`.

`run_pending()` executes only retries whose deadline is reached.

## Concurrency interaction

LOT-14 intentionally treats every admitted non-terminal Execution as consuming capacity:

```text
QUEUED
RUNNING
RETRY_WAIT
```

LOT-15 preserves that guarantee.

This is conservative: a retry-waiting execution keeps its concurrency reservation, preventing a future retry from re-entering above the configured max-instance limit.

A future concurrency-policy extension may explicitly support releasing capacity while waiting, but LOT-15 does not weaken LOT-14 guarantees.

## Public API

```python
scheduler.add_schedule(
    target=my_job,
    trigger=my_trigger,
    retry=RetryPolicy(
        max_attempts=3,
        backoff=FixedBackoff(Duration.seconds(5)),
    ),
)
```

Public exports include:

```text
RetryPolicy
RetryDecision
RetryDecisionReason
NoBackoff
FixedBackoff
ExponentialBackoff
```

## RunPendingResult

A failed Attempt that is scheduled for retry is not reported as a terminal workload failure.

```text
result.retry_scheduled
result.failed
result.succeeded
```

`failed` counts terminal unsuccessful Executions only.

## Qualification

LOT-15 qualifies:

- neutral retry policy;
- invalid max-attempt values;
- fixed backoff;
- exponential growth and capping;
- retryable failure decisions;
- non-retryable hints;
- retryable-hint override;
- permanent failures;
- attempts exhaustion;
- durable RETRY_WAIT state;
- deadline-aware runnable query;
- same Execution identity across attempts;
- incrementing Attempt numbers;
- public fail → wait → success flow;
- public retries-exhausted flow.

## Non-goals

LOT-15 does not implement:

- execution timeout enforcement;
- cancellation refinements;
- jitter;
- arbitrary executable retry predicates;
- SQL persistence;
- crash reconciliation;
- distributed retry claims;
- multi-worker coordination.

## Exit criteria

LOT-15 is complete when:

- retry configuration is immutable and declarative;
- retry policy snapshots survive Schedule changes;
- retries reuse the logical Execution;
- Attempts remain individually durable;
- retry backoff is deadline-based and non-blocking;
- run_pending resumes due retries;
- terminal exhaustion is explicit;
- public API exposes retry configuration;
- unit, integration, E2E, lint, format, typing, and test gates are green.

## Next

`LOT-16 — Execution Timeout`
