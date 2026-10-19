# V1-01.F — Compatibility & Deprecation Policy

**Scope:** stable Python API, stable secondary namespaces, typing, documented runtime
semantics and the deprecation lifecycle that applies once PyScheduleKit 1.0.0 is activated.

**Runtime behavior changed:** no  
**Version changed:** no

## Objective

V1-01.F defines the compatibility promise that PyScheduleKit will make for the complete 1.x
major line.

Earlier V1-01 lots froze the candidate names, namespace placement, callable signatures,
Protocols, Enums and exception catch categories. This lot answers the policy question behind
those snapshots:

> Which changes are compatible inside 1.x, which changes require deprecation, and which
> changes are reserved for the next major version?

The machine-readable source of truth is
`src/pyschedulekit/api/_manifest.py`. The executable guard is
`tests/architecture/test_v1_compatibility_policy.py`.

## Stable compatibility promise

After 1.0.0, the documented stable surfaces are protected by Semantic Versioning for the
lifetime of the 1.x major line.

The stable compatibility domain includes:

- the public names selected for `pyschedulekit` and `pyschedulekit.api`;
- callable signatures and calling modes;
- exported Protocol members;
- Enum member names and serialized values;
- public exception catch categories;
- public result/snapshot fields once V1-01.G records their executable baseline;
- documented runtime semantics;
- public typing contracts;
- stable secondary namespaces:
  - `pyschedulekit.postgres`;
  - `pyschedulekit.testing`;
- root metadata whose stable presence is explicitly promised, including `__version__`.

`pyschedulekit.experimental` and unlisted implementation submodules remain outside this
stable promise.

## Versioning rules

### Patch releases

A patch release may contain compatible bug fixes, security hardening, documentation
corrections and internal refactoring.

A bug fix may change behavior that was observably wrong when the new behavior restores an
already documented stable contract. Such corrections must be called out when they could
surprise consumers.

Patch releases must not intentionally add a new stable public capability or introduce a
breaking public change.

### Minor releases

A minor release may add stable public capabilities when existing valid consumer code remains
valid and preserves its documented meaning.

Examples include:

- a new public class or method;
- a new optional keyword parameter with a compatible default;
- a new stable testing helper;
- a new optional PostgreSQL export;
- widening an accepted input contract without invalidating existing calls.

Additive changes must not silently alter the meaning of an existing call.

### Major releases

A change that breaks the stable public contract is reserved for the next major version.

Deprecation during 1.x may prepare consumers for that future change, but deprecation does not
authorize removal inside the same major line.

## Breaking change classes

The following are breaking unless a stronger compatible rule can be demonstrated:

- removing or renaming a stable public name;
- renaming a public parameter;
- turning an optional parameter into a required parameter;
- restricting positional/keyword calling compatibility;
- changing an established default in a way that changes existing meaning;
- narrowing an accepted input contract;
- widening a return contract in a way that invalidates existing consumer assumptions;
- removing an exported Protocol member;
- removing or renaming an Enum member;
- changing a serialized Enum value;
- changing a documented public exception catch category;
- removing a stable public result/snapshot field;
- changing documented runtime behavior incompatibly;
- changing public annotations so previously valid consumer typing becomes invalid.

An implementation refactor is not a breaking change merely because an internal module,
private helper or non-public type changes.

## Typing compatibility

PyScheduleKit ships inline typing through PEP 561. Stable public typing is therefore part of
the compatibility contract.

The governing rule is:

> Consumer code that is valid against the supported public typing contract should remain
> valid throughout the same major line unless the code depends on an experimental or
> explicitly internal surface.

In particular:

- narrowing accepted parameter types is breaking when it rejects previously valid typed use;
- adding `None` or another alternative to a return type can be breaking when consumers were
  previously entitled to assume a narrower result;
- widening accepted input types can be additive;
- implementation-only annotation refactoring does not create a compatibility promise.

V1-01.D and V1-01.E protect callable and Protocol structure. V1-01.G completes the exact
field-level structural baseline for returned public snapshots/results.

## Behavioral compatibility

The compatibility promise is not limited to import names and signatures.

Behavior becomes stable when it is both:

1. documented as supported behavior; and
2. mapped to executable qualification.

Examples include:

- scheduler state-transition semantics;
- deterministic trigger behavior;
- public policy semantics;
- documented result meanings;
- exception categories;
- ordering, deduplication or identity guarantees when explicitly documented.

A consumer relying on an undocumented implementation accident does not create a new
compatibility promise.

## Deprecation lifecycle

Stable API removal follows this lifecycle:

```text
stable API
    ↓
replacement or migration guidance introduced
    ↓
PyScheduleKitDeprecationWarning
    ↓
at least one prior stable release containing the deprecation
    ↓
next major version boundary
    ↓
removal may occur
```

A stable deprecation requires:

- `PyScheduleKitDeprecationWarning` when runtime warning is applicable;
- migration guidance or an explicit removal rationale;
- a changelog entry;
- at least one previously published stable release carrying the deprecation before removal;
- removal only at a major-version boundary.

A deprecation may remain available for the rest of 1.x. It must not be removed merely
because one minor release has elapsed.

Deprecation messages should identify the affected surface and, when available, the supported
replacement.

## Pre-1.0 legacy redirects

The 11 legacy root redirects to `pyschedulekit.experimental` are a pre-1.0 transition and
are not protected by the future 1.x deprecation window.

V1-01.C already decided:

```text
LEGACY_ROOT_REDIRECT_V1_POLICY = "remove-before-v1.0.0"
```

Their removal therefore belongs to V1-01.H before the stable contract is activated.

No new legacy redirect should be introduced to avoid making the final 1.0 root larger than
the reviewed 63-name convenience surface.

## Experimental and internal surfaces

### `pyschedulekit.experimental`

Experimental names may change, move or disappear without the normal stable deprecation
window.

Changes must still be deliberate and recorded in the changelog. Promotion from experimental
to stable requires an explicit contract review.

### Internal modules

Unlisted modules and symbols are implementation details for compatibility purposes.

Importability alone does not make a module stable. Consumer imports from internal
`domain`, `application`, `ports` or `infrastructure` paths are outside the SemVer
promise unless that symbol is explicitly re-exported through a stable public namespace.

## Persistence compatibility boundary

Persisted data compatibility is a separate but related contract.

V1-02.A now defines the exact minimum readable versions for SQLite schema, shared SQL
value codecs, ScheduleDefinition, Trigger envelopes, calendar codecs/provider schema and
PostgreSQL schema evolution.

V1-01.F established the governing rule in advance, and V1-02.A applies it:

> The declared 1.x persistence read floor is protected for the remainder of the 1.x major
> line.

Every currently versioned persistence surface has a frozen floor of v1. Raising that floor
inside 1.x is a breaking compatibility event. Unknown future persisted versions continue to
fail closed unless an explicit migration exists.

See [V1-02.A Persistence Version Floor & Policy](./V1-02A_PERSISTENCE_VERSION_FLOOR_AND_POLICY.md).

## Machine-readable policy

`src/pyschedulekit/api/_manifest.py` records:

- `V1_STABLE_COMPATIBILITY_POLICY`;
- `V1_DEPRECATION_POLICY`;
- `V1_PROTECTED_CONTRACT_ELEMENTS`;
- `V1_BREAKING_CHANGE_CLASSES`.

The core rules are:

```text
stable public API          → SemVer protected within one major
additive stable API        → minor or major release
compatible bug fix         → patch, minor or major release
breaking public change     → next major only
public typing              → previously valid consumer typing remains valid
persistence floor          → frozen for the major after V1-02 defines it

deprecation warning        → PyScheduleKitDeprecationWarning
migration guidance         → required
changelog entry            → required
minimum prior releases     → 1 stable release
removal boundary           → next major only
```

## Executable evidence

`tests/architecture/test_v1_compatibility_policy.py` enforces:

- the exact stable compatibility policy;
- the exact deprecation policy;
- the protected contract categories;
- the explicit breaking-change classes;
- references to this canonical document from project guidance, API, architecture and release
  documentation.

## Deliberate boundary

V1-01.F does not:

- change runtime behavior;
- change the package version;
- apply the compact 63-name root;
- remove the 11 pre-1.0 legacy redirects;
- freeze the exact fields of all public result/snapshot objects;
- choose the persistence compatibility floor;
- create a tag, release or PyPI publication.

Those concerns remain assigned to V1-01.G, V1-01.H and V1-02 through V1-05.

---

**Status:** V1-01.F complete once the policy guard and documentation references pass the full
CI/distribution matrix. Next: **V1-01.G — Executable Contract Snapshots**.
