# V1-01.E — Protocol / Enum / Exception Freeze

**Scope:** exported structural extension contracts, public enum values and public exception
categories.

## Objective

V1-01.E completes the structural part of the 1.x public contract after V1-01.D froze
consumer-facing callable signatures.

This lot makes three compatibility promises executable:

1. exported Protocol members do not drift silently;
2. public Enum names and serialized values remain stable;
3. public exception categories remain catchable through the documented hierarchy.

## Protocol contracts

The freeze covers the exported structural extension points:

- `Trigger`;
- `CalendarProvider`;
- `CancellationToken`;
- `Clock`;
- `Executor`;
- `PreparedTarget`;
- `ObservationSink`;
- `OutboxPublisher`;
- `UnitOfWorkFactory`.

For methods, CI freezes parameter name, positional/keyword mode and defaults. For property
contracts it freezes the property member itself.

Representative contracts include:

```python
class Trigger(Protocol):
    def next_after(self, reference: Instant) -> Instant | None: ...

class Clock(Protocol):
    def now(self) -> Instant: ...

class CalendarProvider(Protocol):
    def resolve(
        self,
        reference: CalendarRef,
        *,
        revision: CalendarRevision | None = None,
    ) -> BusinessCalendar: ...

class CancellationToken(Protocol):
    @property
    def is_cancelled(self) -> bool: ...

    def raise_if_cancelled(self) -> None: ...
```

The deeper persistence repository Protocols remain internal implementation contracts and are
not promoted into the 1.x consumer promise merely because they exist in source.

## Enum contracts

The exact member names, values and order are frozen for 14 public Enums:

- `ConcurrencyDecisionAction`;
- `ConcurrencyMode`;
- `ConcurrencyOverflowPolicy`;
- `CronAmbiguousTimePolicy`;
- `CronDialect`;
- `CronNonexistentTimePolicy`;
- `ExecutionState`;
- `FailureCategory`;
- `HttpMethod`;
- `MisfirePolicyAction`;
- `OutboxState`;
- `RetryDecisionReason`;
- `ScheduleState`;
- `ShutdownMode`.

This matters beyond Python syntax because several values appear in persisted configuration,
operational results, logs, observations and integration payloads.

For example:

```text
ExecutionState.RETRY_WAIT = "retry_wait"
FailureCategory.TIMEOUT   = "timeout"
ScheduleState.CANCELLED   = "cancelled"
ShutdownMode.CANCEL       = "cancel"
```

Changing one of those string values is therefore treated as a compatibility event rather than
an internal refactor.

## Exception contract

The stable exception model is frozen by **catch category**, not by every internal intermediate
base class.

The canonical public categories remain:

```text
PyScheduleKitError
├── PyScheduleKitConfigurationError  + ValueError
├── PyScheduleKitStateError          + RuntimeError
├── PyScheduleKitNotFoundError       + LookupError
└── PyScheduleKitTargetError         + RuntimeError
```

Specific public exceptions are qualified against their stable categories, including:

- `ScheduleNotFoundError` / `ExecutionNotFoundError` → not-found category;
- `RuntimeAlreadyRunningError` → state/runtime category;
- crash-recovery and reconciliation active/incomplete errors → state/runtime category;
- `TargetResolutionError` / `UnsupportedTargetError` → target/runtime category;
- `ExecutionCancelledError` → runtime error;
- optional PostgreSQL `TransientPersistenceError` → runtime error;
- testing `TriggerContractViolation` → assertion category.

`PyScheduleKitDeprecationWarning` remains a `DeprecationWarning`, not a
`PyScheduleKitError`.

## Error-named diagnostic records

Three exported names intentionally contain `Error` but are not exceptions:

- `CrashRecoveryError`;
- `OutboxPublishError`;
- `RunPendingError`.

They are structured data returned inside operational results.

V1-01.E freezes that distinction. Turning one into an exception would change how consumer code
handles operational diagnostics and therefore requires an explicit compatibility decision.

## Executable evidence

`tests/architecture/test_v1_protocol_enum_exception_freeze.py` enforces:

- Protocol method shapes;
- Protocol property members;
- exact Enum names, values and order;
- public exception catch categories;
- the deprecation-warning category;
- diagnostic `*Error` records remaining non-exceptions.

## Deliberate boundary

V1-01.E does not yet:

- publish the canonical compatibility/deprecation policy;
- define the minimum deprecation window;
- apply the final 63-name compact root;
- remove the 11 legacy root redirects;
- snapshot all returned dataclass fields.

Those are handled by the remaining V1-01 lots.

---

**Status:** V1-01.E complete once the executable baseline passes CI/distribution.
Next: **V1-01.F — Compatibility & Deprecation Policy**.
