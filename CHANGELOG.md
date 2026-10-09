# Changelog

All notable changes to PyScheduleKit will be documented in this file.

The project follows Semantic Versioning once public contracts begin to stabilize.

## [Unreleased]

### Added

- Added CAL-03 Business-Day Trigger Semantics with public `BusinessDayTrigger` support for positive/negative monthly working-day ordinals, Schedule-local civil time, exact versioned calendars, explicit DST policies, bounded search, declarative persistence, and Memory/SQLite/PostgreSQL parity qualification.

- Added CAL-02 Calendar-aware Occurrence Planning: exact calendar revisions are resolved through `CalendarProvider`, Trigger candidates are filtered by the Schedule's local business date, `next_run_time` skips excluded dates, catch-up/coalesce ignore non-occurrences, legacy CAL-01 raw checkpoints self-heal, and candidate scanning is bounded/fail-closed.

- Added CAL-01 Schedule Calendar Binding: `ScheduleDefinition` and `Scheduler.add_schedule()` can carry an exact optional `CalendarSnapshotRef`; the binding is visible through `ScheduleSnapshot`, round-trips across InMemory/SQLite/PostgreSQL, and remains backward-compatible with legacy schedule JSON while deliberately not changing trigger timing until CAL-02.

- Added CAL-00 calendar foundations: `CalendarRef`, `CalendarRevision`, `CalendarSnapshotRef`, immutable `BusinessCalendar`, `CalendarProvider`, and a thread-safe version-aware `InMemoryCalendarProvider` without yet changing Schedule persistence or trigger semantics.

- Added `ExecutorRegistry` as an instance-owned, thread-safe extension point for explicit custom executors, with dynamic RoutingExecutor resolution, exact-identity unregister, Scheduler isolation, and no global/import-time plugin discovery.

- Added `AsyncioExecutor` and `AsyncPythonTargetRegistry` for trusted `async def` workloads, including automatic Scheduler detection, timeout/cancellation/fencing integration, durable retry reuse, and `python_async` target references without changing the synchronous Executor protocol.
- Added PostgreSQL PG-05 production hardening: deterministic write ordering, READ COMMITTED transaction semantics, explicit transient concurrency errors, application-owned connection/pool hooks, PostgreSQL 16/17/18 CI qualification, PostgreSQL-vs-SQLite benchmark evidence, migration/support policy, and the stable optional `pyschedulekit.postgres` namespace.
- Added PostgreSQL PG-04 live Scheduler and multi-worker qualification covering durable `run_pending()`, retry, transactional outbox, reconciliation, crash recovery, admission-lock contention, materialization-lease contention and expired-claim takeover; 138 PostgreSQL tests pass at 88.59% adapter coverage.

- Added PostgreSQL PG-03 shared adapter-parity qualification: the same observable contract now targets InMemory, SQLite and live PostgreSQL for referential integrity, atomic graphs, staged state, rollback, duplicate translation, optimistic CAS, temporal queries, coordination, outbox and retention; PostgreSQL coverage is gated at 85% and PG-03 qualifies at 87.88% across 130 live-service tests.

- Added PostgreSQL PG-02 internal coordination, outbox and retention repositories plus a full nine-repository UnitOfWork, still withheld from the stable public API pending parity and Scheduler E2E qualification.

- Added PostgreSQL PG-01 internal core repositories for Schedule, ExecutionRequest, Execution and Attempt with staged UnitOfWork semantics, identity map, rollback, duplicate translation and optimistic compare-and-swap qualification.

- Added PostgreSQL PG-00 foundation: optional Psycopg 3 support, native TIMESTAMPTZ schema, advisory-lock bootstrap, concurrent/idempotent schema qualification, and a live PostgreSQL CI service.

- Added a deterministic five-scenario chaos/fault-injection campaign covering executor retry recovery, outbox broker failure, runtime cycle supervision, admission-lock persistence conflicts, and stale-owner fencing.
- Added a dedicated Chaos Qualification workflow that archives machine-readable campaign evidence after chaos-relevant merges to main.

- Added a reproducible benchmark harness for interval, cron, in-memory/SQLite cycles, and 1k→10k idle-scheduler scaling; smoke correctness runs in PR CI while standard benchmark evidence is archived after benchmark-relevant merges to main.
- Added installed-distribution dogfooding across wheel/sdist × Python 3.11/3.12/3.13, exercising cron, retry, SQLite durability and readiness outside the source checkout.
- Added a stable public API reference backed by an architecture test that requires every manifest export and legacy compatibility name to remain documented.
- Added a runnable five-scenario cookbook covering interval scheduling, cron/timezones, retry/backoff, SQLite durability, and health/readiness.
- Added acceptance tests that execute every cookbook script under CI.

### Changed

- Deferred all future PyPI publication until the first stable `1.0.0`; pre-1.0 and prerelease versions remain development-only milestones qualified by CI.
- Added an executable release policy gate so only canonical stable semantic versions `>=1.0.0` can reach the PyPI publishing job.
- Reorganized current documentation under `docs/`, with `docs/README.md` as the canonical navigation hub and dated audit snapshots under `docs/audit/2026-10-08/`.
- Added repository-wide local Markdown link integrity qualification while excluding raw archived audit transcripts.


## [0.1.0a4] - 2026-10-09

### Fixed

- Hardened `run_pending()` against concurrent execution-state transitions and added continuous-runtime failure supervision so isolated cycle failures no longer terminate the scheduler.
- Made SQLite schema bootstrap idempotent and concurrency-safe under simultaneous initializers.
- Released admission locks deterministically after persistence conflicts to avoid artificial TTL stalls.
- Aligned InMemory and SQLite persistence semantics through shared adapter parity contracts, including referential integrity and staged-state visibility.
- Hardened HTTP response cleanup and redirect handling with bounded same-host HTTP(S) redirects and deterministic failure cleanup.
- Compensated implicit local target registrations when schedule creation fails, preventing orphan registry state after validation or persistence errors.

### Changed

- Enforced an 85% branch-aware coverage floor and pinned Ruff / GitHub Actions for reproducible CI.
- Integrated public-package acceptance qualification into the maintained test surface.
- Consolidated the 2026-10-08 OpenCode audit into a dated snapshot plus an authoritative B1-B12 remediation register.
- Archived raw audit transcripts under `docs/audit/2026-10-08/sessions/` and removed them from the production Ruff surface.
- Aligned release-readiness checks with the production pipeline: qualification → PyPI Trusted Publishing → PyPI verification → immutable GitHub prerelease.


## [0.1.0a3] - 2026-10-08

### Changed

- Streamlined release workflow to publish directly to PyPI via Trusted Publishing OIDC, aligning with `pyworkflowkit` and `pytransformkit`.
- Bumped package version to `0.1.0a3`.

## [0.1.0a2] - 2026-10-08

### Fixed

- Corrected the `pypa/gh-action-pypi-publish` action commit SHA to valid release commit `dc37677b2e1c63e2034f94d8a5b11f265b73ba33` (v1.14.2) in `.github/workflows/release-candidate.yml` and related tests/documentation.
- Incremented package version to `0.1.0a2` following release runbook fix-forward discipline after `v0.1.0a1` publishing failure.

## [0.1.0a1] - 2026-10-08

### Added

- Manual Release Readiness rehearsal workflow that never creates or pushes a release tag.
- Executable release preflight covering version identity, frozen changelog, and external-control acknowledgements.
- Explicit GO / NO-GO checklist for the first real release.
- Deterministic failure/retry/recovery matrix across qualification, TestPyPI, PyPI, and GitHub Release stages.
- Yank-and-fix-forward policy for defective published artifacts; published versions are never overwritten.
- Immutable Release recovery discipline and security-incident release procedure.

- GitHub artifact build-provenance attestations for tagged wheel/sdist release candidates.
- SHA-pinned official `actions/attest` integration with tag-only provenance generation.
- GitHub prerelease creation only after successful production PyPI verification.
- Exact qualified wheel, sdist, and SHA-256 manifest attachment to the GitHub Release.
- Existing-tag enforcement, generated release notes, prerelease semantics, and latest-release suppression for alpha versions.
- Consumer-side GitHub Release verification through asset re-download, checksum validation, and attestation verification.
- Release workflow fitness tests covering provenance permissions, no rebuild, exact assets, and post-release verification.
- Immutable Releases documented as a preflight hardening requirement for first production release.

- Production PyPI Trusted Publishing downstream of successful TestPyPI verification.
- Dedicated `pypi` GitHub environment and job-scoped OIDC permission for production publication.
- Exact qualified artifact reuse and checksum verification before PyPI upload.
- SHA-pinned official PyPA publishing action with PEP 740 attestations enabled for production.
- Post-publish reinstall and smoke verification from the canonical PyPI simple index.
- Release workflow fitness tests enforcing TestPyPI-before-PyPI promotion, no rebuild, and no static credentials.

- TestPyPI Trusted Publishing job using GitHub OIDC with no static package-index credential.
- Dedicated `testpypi` GitHub environment binding for the publisher identity.
- SHA-pinned official PyPA publishing action with PEP 740 attestations enabled.
- Exact retained release-candidate artifact reuse and checksum verification before upload.
- Post-publish installation and smoke verification from the TestPyPI simple index.
- Bounded TestPyPI indexing retry to distinguish propagation delay from publication failure.
- Workflow fitness tests preventing rebuilds, static credentials, or OIDC/environment drift.

- Canonical release-candidate tag gate enforcing `v<package-version>`.
- Release tag/source/artifact version identity verification before publication.
- Main-line ancestry check for real tag-triggered release candidates.
- Release-candidate SHA-256 checksum manifest and 30-day artifact retention.
- Unit qualification for canonical tags, malformed tags, mismatch short-circuiting, and artifact delegation.
- Pull-request dry-run of the release-candidate gate through Distribution Qualification.
- Dedicated tagged `Release Candidate Gate` workflow with no publication side effects.

- Release-engineering roadmap separated from the functional LOT roadmap.
- Dedicated `release` optional dependency group with `build` and `twine`.
- Wheel + sdist qualification through `python -m build`.
- Strict distribution metadata and README validation with `twine check --strict`.
- Artifact-level wheel/sdist contract verifier including PEP 561 marker checks.
- Clean-install smoke qualification for wheel and sdist on Python 3.11, 3.12, and 3.13.
- GitHub Actions distribution artifact retained for downstream publication without rebuilding.

- Explicit stable API manifest shared by `pyschedulekit.api` and root convenience exports.
- `pyschedulekit.experimental` namespace for low-level coordination primitives.
- Deprecated compatibility shims for legacy root-level experimental imports.
- Stable `PyScheduleKitError` hierarchy for configuration, state, lookup, and target errors.
- Immutable public run-pending snapshots that no longer leak mutable Execution aggregates.
- Immutable `Scheduler.cancel_execution()` result via `ExecutionSnapshot`.
- End-to-end typed public result coverage for `RequestId`, `AttemptId`, decisions, failures, and policies.
- Public Scheduler signature fitness tests and exact export-manifest tests.
- PEP 561 `py.typed` packaging marker.
- Single-source package version metadata and version `0.1.0a1`.
- LOT-34 public API contract, deprecation, typing, signature, and version qualification.
- `RoutingExecutor` for explicit target-kind dispatch.
- Dependency-free `HttpExecutor`, `HttpTargetRegistry`, `HttpRequestSpec`, and `HttpMethod`.
- Public Scheduler HTTP-target registration and custom executor injection.
- Executor-port idempotency-key propagation from durable Execution identity.
- HTTP `Idempotency-Key` and `X-PyScheduleKit-Fencing-Token` propagation.
- Normalized HTTP status, transport, timeout, and cancellation failure semantics.
- `target_kind` on execution-attempt observations.
- LOT-33 routing, HTTP, retry, metadata propagation, custom-executor, and end-to-end qualification.
- Explicit `RetentionPolicy` and `Scheduler.cleanup()` operational API.
- Transactional bounded cleanup for terminal Execution graphs and terminal orphan requests.
- Published-only outbox retention; pending outbox messages are never cleanup candidates.
- Global logical cleanup budget with structured `CleanupResult` counts.
- `retention.cleanup.completed` structured observation.
- SQLite schema v8 with indexed `executions.completed_at` and retention indexes.
- Automatic v7 to v8 completion-time backfill from durable execution result JSON.
- In-memory, SQLite, migration, budget, active-state safety, and end-to-end LOT-32 qualification.
- Immutable ScheduleSnapshot and ExecutionSnapshot operational views.
- Public Scheduler inspection for Schedule and Execution state without leaking aggregates.
- Transactional pause_schedule(), resume_schedule(), and cancel_schedule() controls.
- Explicit SchedulerHealth liveness report and SchedulerReadiness startup-barrier report.
- Non-mutating persistence health probing.
- Durable SQLite operational-control qualification across Scheduler restarts.
- Public ScheduleState, ScheduleNotFoundError, ExecutionNotFoundError, and operational report exports.
- LOT-31 unit, SQLite integration, and end-to-end operational API qualification.

- Dependency-neutral Observation and ObservationSink public contracts.
- Best-effort Observer isolation so telemetry failures never break scheduling.
- Thread-safe InMemoryObservationSink reference adapter.
- Structured scheduler.cycle.completed aggregate cycle observations.
- Structured execution.attempt.completed lifecycle observations.
- Continuous-runtime cycle and wake-delay observations.
- Public Scheduler(observation_sink=...) integration.
- LOT-30 unit, runtime, and end-to-end observability qualification.

- Schedule-scoped durable materialization leases for multi-worker SchedulerEngine ownership.
- Monotonic materialization fencing generations and stale-owner rollback.
- Atomic Schedule checkpoint / ExecutionRequest / lease-release commits.
- Explicit materialization coordination denial in SchedulerEvaluationResult and RunPendingResult.
- Ongoing lease-aware crash recovery during every scheduling cycle.
- SQLite schema v7 with schedule_materialization_leases.
- LOT-29 domain, SQLite, fencing, migration, and no-restart recovery qualification.

- Renewable Execution leases spanning the full RUNNING Attempt.
- Monotonic fencing generation for Execution claims and Schedule admission locks.
- Execution lease heartbeat with configurable interval.
- Fenced Attempt start and terminal lifecycle persistence.
- Fencing-token propagation through the Executor port and trusted Python callables.
- Lease-aware crash recovery that preserves actively owned RUNNING work.
- Recovery takeover with stale-worker terminal-write rejection.
- Atomic admission-lock release plus business-decision CAS fencing.
- SQLite schema v6 and v5 -> v6 generation migration.
- LOT-28 lease, heartbeat, recovery, fencing-token, and stale-admission qualification.

- Durable ScheduleAdmissionLock model and repository.
- Schedule-scoped distributed count-and-admit serialization.
- Scheduler admission_lock_ttl configuration with 5-second default.
- SQLite schema v5 and v4 -> v5 migration.
- Separate RunPendingResult admission_lock_denied_request_ids visibility.
- Multi-worker max_instances qualification across shared SQLite workers.

- Durable ExecutionClaim model with WorkerId and opaque ClaimToken.
- ExecutionClaimRepository integrated into in-memory and SQLite UnitsOfWork.
- SQLite schema v4 with execution_claims and automatic v3 -> v4 migration.
- ExecutionClaimCoordinator for bounded acquisition and expired takeover.
- Atomic claim consumption during Attempt start.
- Scheduler worker_id and configurable claim_ttl.
- Claim contention visibility through RunPendingResult.claim_denied_execution_ids.
- LOT-26 unit, SQLite integration, migration, stale-owner, and multi-worker qualification.

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
