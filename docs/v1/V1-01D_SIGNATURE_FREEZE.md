# V1-01.D — Constructor / Method Signature Freeze

**Scope:** consumer-authored constructors, factories and documented callable methods  
**Executable baseline:** 39 constructors + 53 methods  
**Runtime behavior changed:** no

## Objective

V1-01.D turns the public callable shape into an executable 1.x compatibility baseline.

V1-01.A froze the inventory, V1-01.B decided root versus advanced API placement, and V1-01.C
defined secondary namespace policy. V1-01.D now answers:

> Which argument names, calling modes and defaults are part of the stable consumer contract?

## What is frozen

For each selected callable, CI records:

- parameter name;
- parameter kind:
  - positional-or-keyword;
  - keyword-only;
  - variadic positional;
- required versus optional status;
- stable default values.

A change such as:

```text
limit=100 → limit=500
reference → target_reference
positional-or-keyword → keyword-only
optional → required
```

therefore becomes a deliberate compatibility event rather than an accidental refactor.

## Coverage

The executable baseline covers 39 constructors/factories across:

- time values: `Instant`, `Duration`, `Timezone`, `GracePeriod`;
- built-in triggers: Date, Interval, Cron, BusinessDay and AnyOf;
- schedule references and policies;
- business calendars and local calendar providers;
- HTTP request configuration;
- SQLite persistence;
- advanced executor/registry composition types from `pyschedulekit.api`;
- optional PostgreSQL persistence;
- stable testing helpers;
- the `Scheduler` composition root.

It also covers 53 documented methods/factories, including:

- all current public `Scheduler` commands;
- policy convenience constructors;
- `TargetRef` factories;
- calendar provider registration/resolution;
- executor registry registration/resolution;
- deterministic testing helper methods.

The source of truth is:

```text
tests/architecture/test_v1_signature_freeze.py
```

## Scheduler contract

The existing LOT-34 test already protected Scheduler parameter names. V1-01.D strengthens
that protection by freezing parameter kind and defaults as well.

Examples:

```python
Scheduler(
    *,
    clock=None,
    uow_factory=None,
    calendar_provider=None,
    ...
)

scheduler.add_schedule(
    *,
    target,
    trigger,
    id=None,
    timezone=None,
    calendar=None,
    misfire=None,
    concurrency=None,
    retry=None,
    timeout=None,
)

scheduler.run_pending(*, limit=100)
scheduler.recover(*, limit=1000)
scheduler.shutdown(*, mode=ShutdownMode.WAIT, timeout=None)
```

Changing any of those shapes now requires an explicit compatibility decision.

## Secondary stable surfaces

V1-01.C classified `pyschedulekit.postgres` and `pyschedulekit.testing` as stable
secondary namespaces. Their callable shapes therefore participate in V1-01.D.

Examples include:

- `PostgresUnitOfWorkFactory(dsn, *, connection_provider=None, connection_releaser=None)`;
- `FixedClock(current)`;
- `MutableClock(current)`;
- `TriggerContractSuite.assert_conforms(trigger, references)`;
- `add_request_with_parent(*, uow, request)`.

## Deliberate exclusions

### Returned snapshots and result objects

V1-01.D does not treat framework-returned snapshots/results as user construction APIs merely
because they are dataclasses.

Their public field/member contract is a separate concern and is qualified later by the
structural contract snapshots.

### Protocol members, Enums and exception categories

Those are intentionally assigned to **V1-01.E**.

### Annotation string representation

The runtime `inspect.signature()` annotation representation is not used as the canonical
snapshot. Python versions, postponed annotations and typing implementation details can alter
that representation without changing the practical call contract.

Typing compatibility remains protected through:

- strict mypy on the source tree;
- PEP 561 packaging;
- installed-distribution qualification;
- later explicit protocol/type contract tests.

### Experimental namespace

`pyschedulekit.experimental` remains outside the stable SemVer contract and is therefore
not included in the signature freeze.

## Compatibility rule

Once V1-01 is finalized, a stable 1.x callable may evolve additively only when existing valid
calls remain valid and preserve their meaning.

Breaking changes include, unless handled by the future compatibility/deprecation policy:

- removing or renaming a parameter;
- turning an optional parameter into a required one;
- changing positional/keyword calling compatibility;
- changing a default in a way that changes existing behavior;
- removing a documented factory or method.

## Executable evidence

`tests/architecture/test_v1_signature_freeze.py` compares the live callable signatures
against the curated baseline.

The test intentionally emits both expected and actual shapes on mismatch so a future
maintainer can distinguish an intentional compatibility proposal from accidental drift.

## Deliberate boundary

V1-01.D does not yet:

- freeze Protocol members;
- freeze Enum values;
- freeze exception inheritance/categories;
- apply the 63-name compact root;
- remove legacy root redirects;
- define the minimum deprecation window.

Those are subsequent V1-01 concerns.

---

**Status:** V1-01.D complete once its executable baseline passes the full CI/distribution
matrix. Next: **V1-01.E — Protocol / Enum / Exception Freeze**.
