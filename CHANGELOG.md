# Changelog

All notable changes to PyScheduleKit will be documented in this file.

The project follows Semantic Versioning once public contracts begin to stabilize.

## [Unreleased]

### Added

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
