# Changelog

All notable changes to PyScheduleKit will be documented in this file.

The project follows Semantic Versioning once public contracts begin to stabilize.

## [Unreleased]

### Added

- Transactional outbox message model with deterministic integration identities.
- Outbox repository integrated into in-memory and SQLite UnitsOfWork.
- SQLite schema v3 and automatic v2 → v3 outbox migration.
- Transactional lifecycle messages for Attempt start/completion and cancellation.
- Crash-recovery lifecycle messages emitted in the same recovery transaction.
- Generic OutboxPublisher port and at-least-once OutboxDispatcher.
- Public `Scheduler.dispatch_outbox(...)` API.
- LOT-25 unit, integration, migration, retry, atomicity, and end-to-end qualification.

- Durable graph reconciliation across ExecutionRequest, Execution, and Attempt state.
- Deterministic repair for DISPATCHED requests missing Executions.
- Deterministic request-state repair when a durable Execution already exists.
- Explicit reconciliation issues for unsafe terminal, target, policy, and Attempt-history drift.
- Bounded reconciliation scans with truncation-aware fail-closed semantics.
- Automatic startup ordering: Crash Recovery → Reconciliation → Scheduling.
- Public `Scheduler.reconcile()` and `last_reconciliation_result`.
- LOT-24 SQLite integration and reconstruction-to-SUCCESS end-to-end qualification.

- Persisted crash recovery for orphaned RUNNING Executions and Attempts.
- Automatic recovery barrier before the first Scheduler cycle.
- Explicit CrashRecoveryResult, CrashRecoveryError, and CrashRecoveryIncompleteError APIs.
- RetryPolicy-driven post-crash RETRY_WAIT scheduling with preserved backoff.
- Cancellation-precedence recovery for previously requested cancellations.
- Fail-closed scheduling when persisted RUNNING state cannot be reconciled.
- LOT-23 SQLite restart and successful second-Attempt end-to-end qualification.

- SQLite schema v2 with foreign keys, natural unique constraints, and lifecycle CHECK constraints.
- Automatic transactional migration from LOT-21 schema v1 to schema v2.
- SQL compare-and-swap updates for Schedule, ExecutionRequest, Execution, and Attempt versions.
- Explicit ReferentialIntegrityError and DatabaseInvariantError persistence semantics.
- Atomic rollback qualification for late relational constraint failures.
- LOT-22 relational constraint and migration integration tests.

- SQLite persistence adapter implementing all existing scheduler repositories and UnitOfWork ports.
- Versioned JSON codecs for Schedule definitions, policies, results, and normalized failures.
- Relational persistence for runtime state and wake-up query horizons.
- Shared in-memory SQLite mode and file-backed durable mode.
- Public `SqliteUnitOfWorkFactory` integration with `Scheduler`.
- LOT-21 codec, repository, transaction, reopen, and end-to-end SQLite qualification.

- Graceful shutdown coordination with atomic new-work gating and active Execution tracking.
- Public `ShutdownMode.WAIT` and `ShutdownMode.CANCEL` policies.
- Public `Scheduler.shutdown(...)` with operation-wide timeout and structured `ShutdownResult`.
- Mid-cycle shutdown barriers preventing later Attempts from starting.
- Cooperative cancellation integration for active shutdown cancellation.
- Runtime stopped-event coordination and drain qualification.
- LOT-20 unit and end-to-end graceful shutdown tests.

- Durable-state-driven `WakeUpPlanner` for continuous runtime scheduling.
- Repository horizon queries for next Schedule and retry wake-ups.
- Immediate wake-up for PENDING requests and QUEUED Executions.
- Mutation-driven runtime wake signals after schedule creation and execution cancellation.
- `max_sleep` reconciliation ceiling with backward-compatible `poll_interval` alias.
- LOT-19 wake-up strategy and mutation-interruption qualification.

- Continuous fixed-cadence scheduler runtime built on top of `run_pending()`.
- Interruptible event-based waiting and explicit stop requests.
- Public `Scheduler.run_forever(...)` and `Scheduler.stop()` runtime control.
- Runtime observability through `is_running`, `cycles_completed`, and `last_result`.
- Concurrent-start protection through `RuntimeAlreadyRunningError`.
- LOT-18 unit and end-to-end continuous-runtime qualification.

- Durable cancellation-request metadata on running Executions.
- Thread-safe process-local CancellationToken and controller contracts.
- Cooperative cancellation injection for token-aware Python targets.
- Public `Scheduler.cancel_execution(...)` control-plane API.
- Immediate cancellation for QUEUED and RETRY_WAIT Executions.
- Explicit CANCELLED normalization with retry suppression.
- LOT-17 unit, integration, concurrent and end-to-end qualification.

- Durable per-Attempt execution timeout snapshots from ScheduleDefinition to Execution.
- Optional timeout-aware Executor port and LocalExecutor watchdog enforcement.
- Explicit TIMEOUT failure normalization routed through AttemptState.TIMED_OUT.
- Retry-policy integration for timed-out Attempts without implicit executor retries.
- Public `Scheduler.add_schedule(timeout=...)` support.
- LOT-16 unit, integration, watchdog, and end-to-end timeout qualification.

- Declarative `RetryPolicy` with total-attempt semantics and neutral max_attempts=1 default.
- Built-in `NoBackoff`, `FixedBackoff`, and capped `ExponentialBackoff` strategies.
- Pure `RetryEvaluator` and explicit retry decision reasons.
- Durable retry policy snapshots across ScheduleDefinition, ExecutionRequest, and Execution.
- Deadline-based `RETRY_WAIT` resumption without blocking sleep.
- Runnable execution queries covering queued work and due retries.
- `RunPendingResult.retry_scheduled` with terminal-only failed counting.
- Public `Scheduler.add_schedule(retry=...)` support.
- LOT-15 unit, integration, and end-to-end retry qualification.

- Immutable `ConcurrencyPolicy` with ALLOW/LIMIT modes and QUEUE/DROP overflow behavior.
- Pure `ConcurrencyEvaluator` producing ADMIT, QUEUE, or DROP decisions.
- Durable concurrency policy snapshots on `ExecutionRequest`.
- Terminal `ExecutionRequestState.DROPPED` distinct from cancellation.
- Process-wide serialized `ConcurrencyCoordinator` for local atomic count-and-admit decisions.
- Admission candidate queries covering PENDING and WAITING_ADMISSION requests.
- Non-terminal Execution counting by ScheduleId, including QUEUED, RUNNING, and RETRY_WAIT.
- `RunPendingResult.admissions`, `queued_request_ids`, and `dropped_request_ids`.
- Public `Scheduler.add_schedule(concurrency=...)` support.
- LOT-14 unit, integration, threaded, snapshot, and end-to-end qualification for admission behavior.
- Bounded `OccurrencePlanner.due_backlog()` reconstruction with oldest-first ordering and `has_more`.
- `MisfirePolicy.max_occurrences` with strict positive validation.
- End-to-end Catch-Up batches that reuse durable requests and continue across cycles.
- Exact Coalesce recovery selecting only the latest due occurrence when the full backlog fits within the configured bound.
- Fail-closed Coalesce overflow with `recovery_limit_schedules` and no checkpoint mutation.
- `RecoveryEvaluationRecord` diagnostic evidence for considered and materialized occurrence identities.
- Oldest-first PENDING and QUEUED in-memory processing based on occurrence scheduled time.
- LOT-13 unit, integration, and end-to-end qualification for bounded recovery semantics.
- Explicit lateness classification with ON_TIME, LATE_ELIGIBLE, and MISFIRED states.
- Immutable `MisfirePolicy` with grace period and SKIP, RUN_NOW, CATCH_UP, and COALESCE actions.
- Pure `LatenessClassifier` and `MisfireEvaluator`.
- SchedulerEngine SKIP and RUN_NOW behavior with inspectable misfire decision records.
- Durable-intent precedence when an ExecutionRequest already exists for an occurrence.
- Public Scheduler support for SKIP and RUN_NOW, with advanced recovery modes rejected until LOT-13.
- `RunPendingResult.unsupported_policy_schedules` for lower-level capability diagnostics.
- LOT-12 unit, integration, and end-to-end qualification for grace boundaries and misfire behavior.
- Five-field numeric `CronTrigger` with wildcard, list, range, and step syntax.
- Explicit IANA timezone evaluation with Vixie day-of-month/day-of-week semantics.
- Explicit DST ambiguity policies (FIRST, SECOND, RAISE) and nonexistent-time policies (SKIP, RAISE).
- Bounded eight-year calendar lookup with `CronSearchLimitError`.
- Public Cron exports and Scheduler timezone-consistency validation.
- LOT-04 unit and end-to-end qualification for parsing, leap years, DST, dialect semantics, and `run_pending()`.
- First public `Scheduler` facade with `register_target()`, `add_schedule()`, and `run_pending()`.
- Structured `RunPendingResult` and safe per-request `RunPendingError`.
- End-to-end due Schedule → ExecutionRequest → Execution → Attempt → LocalExecutor flow.
- Recovery of previously durable PENDING requests and QUEUED executions.
- Deterministic `list_queued()` execution query.
- First qualified root API exports for Scheduler, triggers, time values, TargetRef, and run_pending results.
- LOT-11 end-to-end tests covering due/no-due behavior, workload failures, target-resolution isolation, limits, and durable work resumption.
- Executor port with explicit target preparation and normalized invocation outcomes.
- Registry-only synchronous `LocalExecutor` for trusted zero-argument Python callables.
- `PythonTargetRegistry` with duplicate, async, and required-argument validation.
- `ExecutionRunner` that commits RUNNING state before invoking workload code outside transactions.
- Safe normalization of target `Exception` values into UNKNOWN Failures without persisting raw exception messages.
- LOT-10 tests for success, failure, resolution-before-Attempt, crash persistence, and no implicit retry.
- Full `ExecutionRequest` lifecycle: PENDING, WAITING_ADMISSION, DISPATCHED, CANCELLED.
- `Execution` aggregate with QUEUED, RUNNING, RETRY_WAIT and terminal states.
- Numbered `Attempt` entities with immutable terminal `AttemptResult`.
- `ExecutionResult`, normalized `Failure`, `FailureCategory`, `IdempotencyKey`, and minimal `ExecutionPolicySnapshot`.
- `ExecutionService` for transactional dispatch, Attempt start/completion, retry-wait, timeout, and cancellation transitions.
- In-memory Execution and Attempt repositories with optimistic lifecycle version checks and uniqueness constraints.
- Qualification of deferred Schedule/Execution independence scenarios T-SCH-012/013/014.
- Minimal immutable `ExecutionRequest` with deterministic scheduler-created `RequestId`.
- `ExecutionRequestRepository` integrated into the shared UnitOfWork.
- Atomic in-memory commits spanning Schedule checkpoint updates and ExecutionRequest creation.
- `SchedulerEngine` with same-now evaluation, authoritative per-Schedule reload, and conflict isolation.
- Recovery behavior for a durable request whose Schedule checkpoint still points at the same Occurrence.
- LOT-08 integration tests covering atomicity, backlog progression, target snapshots, finite triggers, and conflicts.
- `ScheduleRepository`, `UnitOfWork`, and `UnitOfWorkFactory` persistence ports.
- Transactional `InMemoryUnitOfWork` with explicit commit/rollback semantics.
- In-memory identity map, write set, committed-state cloning, and optimistic concurrency validation.
- Deterministic `list_due()` query for upcoming SchedulerEngine evaluation.
- LOT-07 integration tests covering transaction visibility, rollback, atomic conflicts, due selection, and stale-writer rejection.
- Immutable `Occurrence` and deterministic `OccurrenceKey` value objects.
- Pure `OccurrencePlanner` for current-checkpoint and future occurrence projection.
- LOT-06 qualification tests covering deterministic identity, revision lineage, immutability, and non-mutating planning.
- First `Schedule` Aggregate Root with explicit lifecycle and invariants.
- `ScheduleId`, `ScheduleRevision`, `PersistenceVersion`, `ScheduleState`, `TargetRef`, and immutable `ScheduleDefinition`.
- Pause/resume/cancel/reschedule/checkpoint semantics with explicit definition-versus-persistence versioning.
- LOT-05 Schedule qualification tests for applicable `T-SCH-*` scenarios.
- Immutable `DateTrigger` with finite one-occurrence semantics.
- Anchored fixed-rate `IntervalTrigger` with direct next-occurrence calculation.
- LOT-03 Date/Interval Trigger qualification tests covering progression, drift, and far-future calculation.
- Structural `Trigger` protocol with `next_after(reference) -> Instant | None` semantics.
- Reusable `TriggerContractSuite` for determinism and strict-progression qualification.
- LOT-02 Trigger contract tests.
- Core temporal Value Objects: `Instant`, `Duration`, `Timezone`, `TimeWindow`, and `GracePeriod`.
- Explicit `Clock` port with `SystemClock` production adapter.
- Deterministic `FixedClock` and `MutableClock` testing adapters.
- Explicit DST nonexistent/ambiguous civil-time validation.
- LOT-01 temporal qualification tests.
- Initial repository and packaging foundation.
- Domain-first package boundaries.
- Static architecture fitness tests.
- CI quality gates.
