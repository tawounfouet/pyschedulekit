# 0.2.x — Executor Plugin Registry

`ExecutorRegistry` is the explicit extension point for custom execution adapters.

## Design rules

The registry follows the architecture constraints defined by the target specs:

- one registry per Scheduler/composition root;
- no process-global mutable registry;
- no plugin registration as an import-time side effect;
- no automatic import from a persisted `TargetRef`;
- explicit application-owned registration only.

This keeps tests isolated and allows multiple Scheduler instances with different executor
sets inside one process.

## Built-in executors

A default `Scheduler` registers:

```text
python        → LocalExecutor
python_async  → AsyncioExecutor
http          → HttpExecutor
```

The router does not hard-code those kinds. It resolves the current registry dynamically.

## Register a plugin

A third-party executor only needs to satisfy the existing synchronous `Executor` protocol.

```python
from pyschedulekit import ExecutorRegistry, Scheduler, TargetRef

registry = ExecutorRegistry()
scheduler = Scheduler(executor_registry=registry)

scheduler.executor_registry.register(
    "workflow",
    workflow_executor,
)

scheduler.add_schedule(
    target=TargetRef("workflow", "invoice-close"),
    trigger=...,
)
```

The Scheduler adds missing built-ins to an explicitly supplied registry, but preserves
preloaded registrations.

## Dynamic registration

The `RoutingExecutor` keeps a reference to the registry rather than copying it.

Therefore this is supported:

```python
scheduler = Scheduler()

scheduler.executor_registry.register("workflow", workflow_executor)
# New schedules/attempts can now resolve TargetRef(kind="workflow", ...).
```

No Scheduler reconstruction is required.

## Registration contract

```python
registry.register(kind, executor)
registry.register(kind, executor, replace=True)
registry.unregister(kind)
registry.unregister(kind, expected_executor)
registry.resolve(kind)
registry.contains(kind)
registry.target_kinds
```

Duplicate registration fails unless `replace=True` is explicit.

`unregister(..., expected_executor=...)` uses object identity so compensating cleanup cannot
accidentally remove a replacement executor installed by another component.

Unknown target kinds fail before attempt execution with `UnsupportedTargetError`.

## Compatibility

The existing constructor surface remains valid:

```python
Scheduler(
    executors={
        "workflow": workflow_executor,
    }
)
```

That mapping is treated as an explicit bootstrap override and is loaded into the
Scheduler-owned registry.

For new extension code, prefer `ExecutorRegistry` because it supports instance isolation
and dynamic registration.

## Security boundary

The registry is not a package auto-discovery mechanism.

PyScheduleKit intentionally does not do this:

```text
TargetRef(kind="some.package.plugin")
        ↓
import arbitrary module
        ↓
execute code
```

Persisted target kinds are data. Executable adapters must already be explicitly trusted and
registered by the application composition root.

Python package entry-point discovery may be considered separately in the future, but it
must not weaken that trust boundary.

## Qualification

The executable contract verifies:

- deterministic target-kind snapshots;
- empty/duplicate rejection;
- explicit replacement;
- exact-identity unregister;
- dynamic router mutation;
- unknown-kind failure;
- two registry instances remain isolated;
- two Scheduler instances remain isolated;
- preloaded explicit plugins survive Scheduler bootstrap;
- legacy `executors={...}` still overrides explicitly;
- a third-party `workflow` executor runs end-to-end through `Scheduler.run_pending()`.

This satisfies the target architecture rule that executor plugins are registered at
bootstrap/composition time and T-API-040 registry isolation.

---

**Status:** 0.2.x — Executor Plugin Registry.
