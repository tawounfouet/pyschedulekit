# V1-01.A — Public API Inventory & Classification

**Baseline:** `bcc08c1962587c058506ea5bfeaf74c06d2a0c4e`  
**Development version:** `0.1.0a4`  
**Scope:** public-name inventory and provisional classification only

## Objective

V1-01.A establishes one machine-readable baseline for every consumer-facing PyScheduleKit
namespace before the 1.0 compatibility promise is frozen.

This lot does **not** freeze constructor signatures, Protocol members, Enum values, exception
semantics or persisted formats. It prevents the public-name inventory from drifting while
the remaining V1-01 work reviews those deeper contracts.

## Classification model

| Classification | Meaning during V1-01 |
|---|---|
| `stable-candidate` | intended to enter the 1.x compatibility contract, but still reviewable before the final V1-01 freeze |
| `supported-testing` | intentionally shipped for consumer tests; its exact 1.x compatibility policy remains to be decided |
| `experimental` | intentionally public but carries no stable compatibility promise |
| `internal` | any other package/module path not explicitly inventoried here |

The word **candidate** is deliberate. V1-01 may still remove, demote or reshape a candidate
before `1.0.0`. Only the final V1-01 freeze turns the retained surface into a 1.x promise.

## Namespace inventory

| Namespace | Classification | Exact surface |
|---|---|---:|
| `pyschedulekit` | stable-candidate | 104 API names + `__version__` |
| `pyschedulekit.api` | stable-candidate | 104 API names |
| `pyschedulekit.postgres` | stable-candidate | 2 names |
| `pyschedulekit.testing` | supported-testing | 5 names |
| `pyschedulekit.experimental` | experimental | 11 names |
| every other import path | internal | not inventoried as public |

There are **123 distinct consumer-facing symbol names** in this baseline when
`__version__` is counted once. The 11 experimental names also remain reachable from the
package root through deprecated warning shims, so import locations are not the same thing as
distinct symbol names.

## Machine-readable source of truth

`src/pyschedulekit/api/_manifest.py` now records:

- `STABLE_PUBLIC_NAMES` — 104 root/API candidates;
- `ROOT_METADATA_NAMES` — `__version__`;
- `POSTGRES_PUBLIC_NAMES` — 2 optional PostgreSQL exports;
- `TESTING_PUBLIC_NAMES` — 5 consumer testing helpers;
- `EXPERIMENTAL_PUBLIC_NAMES` — 11 experimental names;
- `PUBLIC_NAMESPACE_CLASSIFICATIONS` — the provisional support class of each namespace.

The primary 104 names remain exactly the existing `STABLE_PUBLIC_NAMES`; V1-01.A does not
add or remove a runtime export.

## Secondary surfaces

### PostgreSQL

`pyschedulekit.postgres` contains exactly:

- `PostgresUnitOfWorkFactory`;
- `TransientPersistenceError`.

It remains a `stable-candidate` optional namespace. The package root must stay importable
with zero runtime dependencies and must never import Psycopg implicitly.

### Testing

`pyschedulekit.testing` contains exactly:

- `FixedClock`;
- `MutableClock`;
- `TriggerContractSuite`;
- `TriggerContractViolation`;
- `add_request_with_parent`.

These are intentionally shipped and used by consumer-facing examples, but V1-01 must still
decide whether their signatures receive the same full SemVer guarantee as the primary API or
a narrower documented testing-support policy.

### Experimental

`pyschedulekit.experimental` contains 11 low-level coordination names. They remain outside
the stable candidate surface. Those same names currently resolve from the root package
through deprecated shims emitting `PyScheduleKitDeprecationWarning`.

The lifetime and removal window of those root redirects is deferred to the compatibility and
deprecation policy work later in V1-01.

## Executable evidence

`tests/architecture/test_public_namespace_inventory.py` enforces:

- exact namespace classifications;
- exact 104 / 1 / 2 / 5 / 11 inventory counts;
- sorted, unique and pairwise-disjoint named surfaces;
- exact `__all__` parity for root/API/PostgreSQL/testing/experimental;
- root/API object identity;
- root metadata presence;
- experimental names remaining outside stable root `__all__`.

Accidental public-name expansion or contraction therefore fails CI during the rest of V1-01.

## Decisions deliberately deferred

V1-01.A does **not** decide:

- which of the 104 primary candidates survive final 1.0 review;
- constructor or method keyword compatibility;
- Protocol-member compatibility;
- Enum-member compatibility;
- dataclass-field compatibility;
- exception hierarchy/category guarantees beyond existing tests;
- minimum deprecation windows;
- lifetime of legacy root redirects;
- final SemVer status of `pyschedulekit.testing`;
- persistence compatibility floors.

## Exit criteria

V1-01.A is complete when every consumer-facing namespace has an explicit classification,
exact names are machine-readable, accidental drift fails CI, and no runtime behavior or
package version has changed.

---

**Status:** V1-01.A complete. Next: **V1-01.B — Root/API Stable Candidate Review**.
