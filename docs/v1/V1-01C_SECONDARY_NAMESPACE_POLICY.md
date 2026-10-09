# V1-01.C — Secondary Namespace Policy

**Scope:** `pyschedulekit.postgres`, `pyschedulekit.testing`,
`pyschedulekit.experimental`, root `__version__`, legacy root redirects and unlisted
submodules.

## Objective

V1-01.C turns the provisional namespace classifications from V1-01.A into explicit 1.x
support policies.

The primary root/API name review remains V1-01.B. This lot answers a different question:

> What compatibility promise does PyScheduleKit make for consumer-facing namespaces that are
> not the primary `pyschedulekit.api` surface?

## Policy summary

| Surface | V1 policy | Compatibility promise |
|---|---|---|
| `pyschedulekit.postgres` | `stable-optional` | SemVer-protected documented API when the optional extra is installed |
| `pyschedulekit.testing` | `stable-testing` | SemVer-protected documented testing helpers, without production-runtime guarantees |
| `pyschedulekit.experimental` | `experimental-no-semver` | intentionally excluded from stable compatibility guarantees |
| root `__version__` | `stable-presence` | attribute remains available and matches installed distribution identity |
| 11 legacy root redirects | `remove-before-v1.0.0` | transitional pre-1.0 shims only; not part of the final 1.x root contract |
| unlisted submodules | `internal-no-compatibility` | importability does not create a compatibility promise |

## PostgreSQL — stable optional namespace

`pyschedulekit.postgres` contains exactly:

- `PostgresUnitOfWorkFactory`;
- `TransientPersistenceError`.

For 1.x this namespace is a stable optional contract.

That means:

- the two documented exports are covered by SemVer once 1.0.0 ships;
- the optional dependency boundary remains explicit;
- importing base `pyschedulekit` must never require Psycopg;
- missing Psycopg support must continue to fail with a normalized
  `PyScheduleKitConfigurationError`;
- PostgreSQL server-version support remains governed by the dedicated support/migration
  policy rather than by accidental implementation behavior.

Adding new PostgreSQL exports can be additive in a minor release. Removing or incompatibly
changing existing stable exports requires the normal compatibility/deprecation process.

## Testing — stable testing namespace

`pyschedulekit.testing` contains exactly:

- `FixedClock`;
- `MutableClock`;
- `TriggerContractSuite`;
- `TriggerContractViolation`;
- `add_request_with_parent`.

These helpers are deliberately distributed for downstream consumer tests and are already
used by the cookbook.

The 1.x promise is therefore stronger than "best effort": documented names and frozen
signatures/semantics are SemVer-protected.

The label `stable-testing` also establishes a boundary:

- these helpers are suitable for deterministic tests and examples;
- they do not carry production throughput, thread-safety or durability guarantees unless
  explicitly documented for a specific helper;
- new helpers may be added in minor releases;
- breaking an existing documented helper follows the stable deprecation policy.

## Experimental — intentionally outside SemVer

`pyschedulekit.experimental` contains the 11 low-level coordination types already inventoried
by V1-01.A.

The namespace remains deliberately public so advanced users can inspect or prototype against
those concepts, but it is excluded from the 1.x compatibility promise.

For 1.x:

- names may be changed, moved or removed without a normal stable deprecation window;
- changes must still be deliberate and recorded in the changelog;
- no stable code should require an experimental import;
- promotion into stable API requires an explicit future contract review.

The word `experimental` is therefore a real compatibility boundary, not merely a folder
name.

## Legacy root redirects — remove before 1.0.0

The same 11 experimental names are currently reachable from the package root through
`__getattr__` compatibility shims that emit `PyScheduleKitDeprecationWarning`.

Those redirects exist only to bridge earlier pre-1.0 development.

V1-01.C decides that they must be removed before the final 1.0 contract is activated.

Rationale:

1. the names were never included in the stable root `__all__`;
2. the project has already provided an explicit `pyschedulekit.experimental` destination;
3. carrying invisible root aliases through all of 1.x would permanently enlarge the
   compatibility surface;
4. 1.0 is the correct boundary for completing a pre-1.0 migration.

The removal itself belongs to the final V1-01 contract application after signature and
deprecation policy work is complete.

## `__version__` — stable presence, changing value

The root `__version__` attribute is part of the stable package metadata contract.

The promise is:

- `pyschedulekit.__version__` exists;
- it matches the installed distribution version;
- its **value** naturally changes from release to release and is not a fixed compatibility
  constant.

## Unlisted submodules are internal

Importability does not imply stability.

Any module or symbol not explicitly covered by:

- the primary root/API manifest;
- `pyschedulekit.postgres`;
- `pyschedulekit.testing`;
- `pyschedulekit.experimental`;
- documented root metadata;

is internal for compatibility purposes.

Examples include implementation modules under `domain`, `application`, `ports` and
`infrastructure`. They remain available to the project test suite and advanced source
inspection, but downstream code imports them at its own compatibility risk.

## Machine-readable policy

`src/pyschedulekit/api/_manifest.py` records:

- `SECONDARY_NAMESPACE_V1_POLICIES`;
- `ROOT_METADATA_V1_POLICY`;
- `LEGACY_ROOT_REDIRECT_V1_POLICY`;
- `UNLISTED_SUBMODULE_V1_POLICY`.

The existing namespace classification also advances:

- PostgreSQL: `stable-optional`;
- testing: `stable-testing`;
- experimental: `experimental`.

## Executable evidence

`tests/architecture/test_v1_secondary_namespace_policy.py` enforces the exact policy values
and exact secondary surface inventories.

The V1-01.A inventory test is updated to reflect the now-decided PostgreSQL/testing
classifications.

## Deliberate boundary

V1-01.C does not yet:

- remove the 11 root redirects;
- prune the root from 104 current exports to the 63 V1 candidates;
- freeze constructor/method signatures;
- freeze Protocol, Enum or exception semantics;
- define the general deprecation minimum window.

Those changes belong to later V1-01 lots.

---

**Status:** V1-01.C complete. Next: **V1-01.D — Constructor / Method Signature Freeze**.
