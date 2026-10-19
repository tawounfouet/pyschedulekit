# V1-01.G — Executable Contract Snapshots

**Scope:** field-level and read-property structure of stable public objects returned by
Scheduler operations or exposed transitively through those results.

**Runtime behavior changed:** no  
**Version changed:** no

## Objective

V1-01.G completes the structural compatibility baseline started by V1-01.D and V1-01.E.

V1-01.D froze how consumers call the API. V1-01.E froze Protocol, Enum and exception
structure. V1-01.F then declared that public result/snapshot fields are SemVer-protected once
1.0.0 is activated.

This lot answers the remaining structural question:

> Which fields and read-only properties may stable consumer code rely on when it inspects
> PyScheduleKit operation results?

## Public result inventory

The exact inventory is recorded in
`src/pyschedulekit/api/_manifest.py::V1_PUBLIC_RESULT_TYPES`.

It contains 21 stable public result structures:

```text
AdmissionSnapshot
CleanupResult
ConcurrencyDecision
CrashRecoveryError
CrashRecoveryResult
ExecutionPolicySnapshot
ExecutionRunSnapshot
ExecutionSnapshot
ExecutorOutcome
Failure
OutboxDispatchResult
OutboxPublishError
ReconciliationIssue
ReconciliationResult
RetryDecision
RunPendingError
RunPendingResult
ScheduleSnapshot
SchedulerHealth
SchedulerReadiness
ShutdownResult
```

These types are not selected merely because they are dataclasses. They are selected because
they are returned directly by stable operations or appear transitively inside those returned
objects.

## Direct Scheduler results

The principal direct operation results include:

```text
Scheduler.inspect_schedule()   → ScheduleSnapshot
Scheduler.inspect_execution()  → ExecutionSnapshot
Scheduler.pause_schedule()     → ScheduleSnapshot
Scheduler.resume_schedule()    → ScheduleSnapshot
Scheduler.cancel_schedule()    → ScheduleSnapshot
Scheduler.cancel_execution()   → ExecutionSnapshot
Scheduler.health()             → SchedulerHealth
Scheduler.readiness()          → SchedulerReadiness
Scheduler.run_pending()        → RunPendingResult
Scheduler.recover()            → CrashRecoveryResult
Scheduler.reconcile()          → ReconciliationResult
Scheduler.dispatch_outbox()    → OutboxDispatchResult
Scheduler.cleanup()            → CleanupResult
Scheduler.shutdown()           → ShutdownResult
```

The public facade may also retain the latest recovery, reconciliation or run-pending result;
those objects use the same frozen structures.

## Transitive result closure

A direct result is only structurally stable if consumers can also rely on the public records
nested inside it.

For example:

```text
RunPendingResult
├── executions
│   └── ExecutionRunSnapshot
│       ├── execution
│       │   └── ExecutionSnapshot
│       │       └── policy_snapshot
│       │           └── ExecutionPolicySnapshot
│       ├── outcome
│       │   └── ExecutorOutcome
│       │       └── Failure?
│       └── retry_decision
│           └── RetryDecision?
├── admissions
│   └── AdmissionSnapshot
│       └── ConcurrencyDecision?
└── errors
    └── RunPendingError
```

Crash recovery, reconciliation and outbox results similarly expose their diagnostic records:

```text
CrashRecoveryResult
└── errors → CrashRecoveryError

ReconciliationResult
└── issues → ReconciliationIssue

OutboxDispatchResult
└── errors → OutboxPublishError
```

V1-01.G therefore freezes the transitive result closure rather than only top-level return
objects.

## Field contract

`tests/architecture/test_v1_result_contract_snapshots.py` records the exact dataclass field
order for every type in the inventory.

Representative examples:

### ScheduleSnapshot

```text
schedule_id
state
revision
persistence_version
next_run_time
target_kind
target_reference
timezone
calendar
timeout_seconds
```

### ExecutionSnapshot

```text
execution_id
request_id
state
created_at
attempt_count
active_attempt_number
next_attempt_at
cancellation_requested_at
is_terminal
target_kind
target_reference
failure_category
failure_code
completed_at
policy_snapshot
```

### RunPendingResult

```text
evaluation_now
materialized_request_ids
executions
schedule_conflicts
unsupported_policy_schedules
recovery_limit_schedules
admissions
errors
claim_denied_execution_ids
materialization_denied_schedule_ids
```

Removing or renaming one of these fields after 1.0.0 is a breaking contract change under
V1-01.F.

Adding a field is not automatically harmless: it must still be reviewed for constructor,
typing, serialization, pattern-matching and consumer compatibility effects before being
treated as additive.

## Read-only property contract

Several result types expose computed read properties that are part of normal consumer
ergonomics even though they are not dataclass fields.

V1-01.G also freezes those names:

- `ExecutionSnapshot.id`;
- `ExecutionSnapshot.cancellation_requested`;
- `RunPendingResult.succeeded`;
- `RunPendingResult.failed`;
- `RunPendingResult.retry_scheduled`;
- `RunPendingResult.queued_request_ids`;
- `RunPendingResult.admission_lock_denied_request_ids`;
- `RunPendingResult.dropped_request_ids`;
- `CrashRecoveryResult.complete`;
- `CrashRecoveryResult.recovered`;
- `CrashRecoveryResult.failed`;
- `CrashRecoveryResult.retried`;
- `CrashRecoveryResult.cancelled`;
- `ReconciliationResult.repaired`;
- `ReconciliationResult.complete`;
- `CleanupResult.total_deleted`;
- `OutboxDispatchResult.published`;
- `OutboxDispatchResult.failed`;
- `ConcurrencyDecision.admitted`;
- `ExecutorOutcome.succeeded`.

Their runtime meaning remains governed by documentation and behavioral tests; this snapshot
protects structural presence.

## What is deliberately not frozen here

V1-01.G does not turn every public dataclass into a returned-result contract.

Consumer-authored configuration/value objects such as `RetryPolicy`, `ConcurrencyPolicy`,
triggers, identifiers and calendar definitions are already protected through the relevant
name/signature/Enum/Protocol contracts.

The lot also does not snapshot internal application result classes that are converted into
public API results before crossing the Scheduler boundary.

## Typing boundary

V1-01.F declares public typing compatibility as part of the 1.x promise.

V1-01.G freezes field and property names, while the existing strict mypy and PEP 561
qualification continue to validate shipped annotations. The final V1-01.H review will check
that the complete stable public contract is coherent before the root/API surface is applied.

## Executable evidence

`tests/architecture/test_v1_result_contract_snapshots.py` enforces:

- exact inventory of structural result types;
- exact field names and order for all 21 types;
- exact public computed-property names where present;
- every result-contract type remains exported by `pyschedulekit.api`.

The test reports expected and actual structures on drift so an intentional compatibility
proposal is distinguishable from accidental refactoring.

## Deliberate boundary

V1-01.G does not:

- change runtime behavior;
- change the package version;
- apply the compact 63-name root;
- remove the 11 pre-1.0 legacy root redirects;
- define persistence compatibility floors;
- create a tag, release or PyPI publication.

Those remaining public-surface actions belong to V1-01.H. Persistence compatibility begins
in V1-02.

---

**Status:** V1-01.G complete once its architecture snapshot passes the full CI/distribution
matrix. Next: **V1-01.H — Final Public Contract Review**.
