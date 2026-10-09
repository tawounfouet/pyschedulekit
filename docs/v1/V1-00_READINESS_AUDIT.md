# V1-00 — 1.0 Readiness Audit

**Audit date:** 2026-10-09  
**Audited commit:** `95fe6dd3a895f0d455d451b0fd2f2d1d5b6b492d`  
**Development version:** `0.1.0a4`  
**Last public version:** `0.1.0a3`

## Executive verdict

PyScheduleKit is functionally mature enough to enter a 1.0 stabilization sequence. Its
domain model, runtime, persistence adapters, public facade, distribution artifacts and
failure campaigns all have strong executable evidence.

The repository is nevertheless **NO-GO for an immediate `v1.0.0` tag**. The remaining
blockers are primarily compatibility and release-contract gaps:

1. there is no canonical long-term compatibility and deprecation policy;
2. the exact 1.0 promise for secondary public namespaces and signatures is not frozen;
3. persistence mechanisms are versioned, but their post-1.0 support floor is not decided;
4. the release workflow still creates and verifies a GitHub prerelease;
5. final release identity, security and platform gates are not yet activated.

No source version, tag, release or public artifact was changed by this audit.

## Scope and method

The audit inspected:

- package metadata and dependency surfaces;
- root, `pyschedulekit.api`, `pyschedulekit.postgres`, `pyschedulekit.testing` and
  `pyschedulekit.experimental` namespaces;
- public API fitness tests and documentation coverage;
- SQLite, PostgreSQL, Schedule-definition, Trigger and calendar codec versions;
- unit, integration, E2E, architecture, acceptance and chaos tests;
- CI, distribution, PostgreSQL, benchmark, chaos and release workflows;
- release preflight, changelog, version identity and 1.0 runbook;
- open GitHub issues and pull requests.

The audit also reran the complete local suite on CPython 3.14.5, including a warning-focused
run, and checked the latest successful GitHub qualifications.

## Verified foundation

| Area | Evidence | Result |
|---|---|---|
| Test inventory | 781 collected tests across 120 test files | PASS |
| Local suite | 748 passed; 33 PostgreSQL tests skipped only because no local DSN was configured | PASS |
| Coverage | 88.90%, above the enforced 85% branch-aware floor | PASS |
| Static quality | Ruff lint/format and strict mypy | PASS |
| Main CI | [run 37969847003](https://github.com/tawounfouet/pyschedulekit/actions/runs/37969847003), Python 3.11/3.12/3.13 | PASS |
| Distribution | [run 37969847111](https://github.com/tawounfouet/pyschedulekit/actions/runs/37969847111), wheel/sdist × Python 3.11/3.12/3.13 | PASS |
| PostgreSQL | [run 37969389811](https://github.com/tawounfouet/pyschedulekit/actions/runs/37969389811), PostgreSQL 16/17/18 | PASS |
| Chaos | [run 37969847059](https://github.com/tawounfouet/pyschedulekit/actions/runs/37969847059) | PASS |
| Benchmarks | [run 37969846883](https://github.com/tawounfouet/pyschedulekit/actions/runs/37969846883), standard profile archived | PASS |
| Secret scanning | GitGuardian check on merged PR #86 | PASS |
| Open repository backlog | zero open GitHub issues and zero open pull requests at audit time | PASS, not adoption evidence |
| Source debt markers | no `TODO`, `FIXME`, `HACK` or `NotImplementedError` in Python product/test tooling | PASS |
| Expected failures | no `xfail`; local skips are limited to live PostgreSQL tests and are exercised in CI | PASS |

## Contract inventory

### Python and packaging

- Python requirement: `>=3.11`;
- classifiers and CI qualification: Python 3.11, 3.12 and 3.13;
- base runtime dependencies: none;
- optional PostgreSQL dependency: Psycopg 3, bounded to `<4`;
- package is PEP 561 typed through `py.typed`;
- distribution shape is `py3-none-any`.

### Public namespaces

| Namespace | Current surface | Current enforcement | 1.0 decision needed |
|---|---:|---|---|
| `pyschedulekit` / `pyschedulekit.api` | 104 stable class names plus root `__version__` | exact sorted manifest, identity tests, API documentation test | review and freeze supported signatures/semantics |
| `pyschedulekit.postgres` | 2 exports | exact `__all__`, optional-dependency and support-matrix tests | include explicitly in compatibility policy |
| `pyschedulekit.testing` | 5 exports | declared `__all__`, cookbook usage | decide stable support level and add exact contract test |
| `pyschedulekit.experimental` | 11 legacy coordination names | deprecation redirects and identity tests | retain no-compatibility promise; decide redirect removal window |

All 104 root/API manifest entries are classes. The Scheduler constructor and method parameter
names are snapshotted, but the broader set of user-constructible class and protocol
signatures does not yet have a curated 1.0 compatibility snapshot.

### Persistence formats

| Surface | Current version | Existing evidence | Open 1.0 question |
|---|---:|---|---|
| SQLite runtime schema | 8 | executable forward migrations from v1 through v8 | which historical versions remain supported for the 1.x lifetime? |
| PostgreSQL runtime schema | 1 | fail-closed verification on PostgreSQL 16/17/18 | formalize the first future migration/rolling-upgrade promise |
| Schedule definition | 3 | v1/v2 reads, v3 writes, semantic migration tests | freeze the minimum readable version for 1.x |
| Trigger envelopes | 1 | strict per-trigger versions, future versions rejected | define additive/change rules |
| Calendar collection/value codec | 1 | strict round trip and future-version rejection | define support duration and deprecation rules |
| SQLite calendar-provider schema | 1 | schema verification and reopen tests | define support duration |

The implementation is strongly versioned. The missing item is the policy that turns those
mechanisms into a long-term consumer promise. Most migration tests construct historical rows
inside the current test suite; committed golden artifacts produced by released versions are
not yet the compatibility source of truth.

## Acceptance-gate assessment

The specification's 1.0 gate requires all announced supported behavior to be green, no
unexplained expected failures, a frozen public contract, versioned persistent formats and
green security gates.

| Gate | State | Assessment |
|---|---|---|
| Announced runtime behavior | GREEN | broad unit/integration/E2E/adapter/chaos evidence |
| No unexplained `xfail` | GREEN | no `xfail`; live PostgreSQL skips are CI-qualified |
| Public compatibility frozen | RED | exact names exist, but policy and full supported signature scope are not frozen |
| Persistent formats versioned | AMBER | mechanisms are strong; support floor and golden compatibility fixtures are missing |
| Security gates | AMBER | secret scanning and hardened behaviors exist; no repository-owned vulnerability gate |
| Stable release behavior | RED | workflow uses `--prerelease` and asserts `isPrerelease=true` |
| Release identity | RED by design | source is `0.1.0a4`; `v1.0.0` preflight correctly fails closed |

## Findings

### V1-F01 — Stable GitHub Release mode is not implemented — P0

The publication policy permits only stable versions `>=1.0.0`, but the release workflow job
is still named `Create GitHub prerelease`, passes `--prerelease --latest=false`, and verifies
`isPrerelease=true`.

**Risk:** a valid stable package could be published to PyPI and then represented incorrectly
on GitHub, after the irreversible publication step.

**Closure:** introduce version-aware stable release behavior, verify `isPrerelease=false`,
qualify it with workflow fitness tests, and rehearse it before a real tag.

### V1-F02 — Compatibility and deprecation policy is not canonical — P0

Current documents say that SemVer compatibility will begin at 1.0, but they do not define:

- what counts as a breaking API or behavioral change;
- whether keyword names, dataclass fields, enum members, Protocol members and exception
  categories are covered;
- the minimum deprecation window;
- typing compatibility expectations;
- the support duration for persisted formats.

**Closure:** V1-01 must add one canonical compatibility policy referenced by the API,
architecture, SDLC and release documents.

### V1-F03 — The full public namespace/signature scope is not frozen — P0

The exact 104-name root/API manifest is protected, and Scheduler signatures are tested.
However, the stable status of the five `pyschedulekit.testing` helpers is ambiguous and the
two-export PostgreSQL namespace is enforced separately rather than covered by one complete
1.0 contract inventory. Constructor and Protocol compatibility is not curated across the
whole public surface.

**Closure:** review every exported name before freezing it; explicitly classify secondary
namespaces; add focused signature/Protocol snapshots for contracts the project is willing to
support throughout 1.x.

### V1-F04 — Persistence compatibility floor lacks a 1.x promise — P0

SQLite migrations, Schedule-definition migration and strict codec versions are executable,
but the repository does not state whether all alpha-era versions remain readable throughout
1.x. Tests synthesize most legacy payloads using current helpers.

**Closure:** define minimum supported versions and upgrade rules, commit golden fixtures from
the public `0.1.0a3` and final pre-1.0 formats, and exercise them across SQLite/PostgreSQL as
applicable.

### V1-F05 — Release identity is intentionally not activated — P0 at V1-05

The package, installed-package smoke script and package tests correctly use `0.1.0a4`; the
changelog has no dated `1.0.0` section and the classifier remains Alpha. Running preflight
for `v1.0.0` fails with a source/tag mismatch, which is the correct fail-closed result.

**Closure:** only after V1-01 through V1-04, update version, classifier, hard-coded package
assertions and changelog atomically, then run Release Readiness on `main`.

### V1-F06 — Python 3.14 is not in the declared qualification matrix — P1

The full suite passes locally on CPython 3.14.5, but CI, clean-install qualification and
package classifiers stop at 3.13 while `requires-python = ">=3.11"` has no upper bound.

**Closure:** add Python 3.14 to CI and wheel/sdist clean-install matrices, update classifiers,
and decide an explicit Python support-window policy.

### V1-F07 — The test suite is not warning-clean on Python 3.14 — P1

A warning-focused full run passes all tests but reports six unraisable `ResourceWarning`
events for SQLite connections. Direct test helpers use `sqlite3.connect(...)` as a context
manager, which commits/rolls back but does not close the connection.

**Risk:** currently localized to qualification code, but warning noise can hide real resource
regressions and prevents a strict warning gate.

**Closure:** close direct SQLite test connections deterministically and add a warning-clean
gate on the newest supported Python.

### V1-F08 — No repository-owned vulnerability gate — P1

The base install has zero dependencies and GitGuardian secret scanning passes. Optional,
development, build and release dependencies still exist, but no checked-in workflow performs
dependency vulnerability review or records its policy.

**Closure:** define the security gate for base and optional extras, add a reproducible
dependency audit or an explicitly documented equivalent, and keep secret scanning.

### V1-F09 — CI platform deprecation warnings remain — P1

Recent successful workflows report that `actions/upload-artifact@v5` targets deprecated
Node.js 20 and that `ubuntu-latest` is scheduled to migrate to Ubuntu 26.

**Closure:** update SHA-pinned artifact actions to a supported release and select/document an
explicit runner policy before the stable release rehearsal.

### V1-F10 — Adoption evidence is internal only — P2

Cookbook, installed-artifact dogfooding, chaos and benchmarks are strong, but no external
feedback/adoption register exists. Zero open issues is not proof of real-world adoption.

**Closure:** run a time-bounded consumer preview using built artifacts, record feedback and
classify every result as blocker, accepted limitation or post-1.0 enhancement.

### V1-F11 — Current SDLC status lagged behind delivery — resolved in V1-00

`docs/SDLC.md` still identified CAL-04/CAL-05 as the current frontier after the complete
CMP-00 through CMP-05 sequence had merged.

**Closure:** V1-00 updates the canonical navigation, SDLC, architecture and agent guidance to
the readiness sequence and links this audit.

## Remediation roadmap

### V1-01 — Public Contract Freeze

- publish the compatibility/deprecation policy;
- review the 104-name root/API surface before it becomes a 1.x promise;
- classify `postgres`, `testing`, `experimental` and `__version__` explicitly;
- freeze supported constructors, methods, Protocol members, enum values and exception
  categories with executable tests;
- decide the lifetime of the 11 legacy root redirects.

### V1-02 — Persistence Compatibility Contract

- define the supported SQLite/definition/Trigger/calendar/PostgreSQL version floor;
- add immutable golden fixtures from released and final pre-1.0 formats;
- qualify forward migration and semantic equivalence;
- document backup, rollback and rolling-upgrade expectations;
- keep cross-adapter data migration explicitly unsupported unless implemented separately.

### V1-03 — Platform, Warning and Security Gates

- qualify Python 3.14 and formalize the Python support window;
- eliminate SQLite `ResourceWarning` events and enforce warning cleanliness;
- add the repository-owned vulnerability/security gate;
- update deprecated artifact actions and runner policy;
- retain the zero-runtime-dependency base contract.

### V1-04 — Consumer and Stable-Release Rehearsal

- type-check and execute an external consumer against clean-installed artifacts;
- run a structured consumer preview and classify feedback;
- finalize 1.0 API, migration, operations and limitation documentation;
- change and test the GitHub Release path in stable mode without creating a public tag;
- rerun CI, PostgreSQL, distribution, chaos and standard benchmarks.

### V1-05 — Final GO/NO-GO and 1.0.0 Activation

- require every V1 finding to be closed or explicitly accepted with rationale;
- atomically set version/classifier/changelog/package assertions to `1.0.0`;
- run Release Readiness on `main` with external controls confirmed;
- make one explicit final GO/NO-GO decision;
- only after GO, create and push the immutable annotated `v1.0.0` tag.

## Explicit non-goals of V1-00

This audit does not:

- change runtime behavior;
- add a new scheduler feature;
- change the package version;
- create a tag or GitHub Release;
- publish to PyPI;
- silently decide compatibility policy on behalf of V1-01.

---

**Status:** V1-00 complete. Overall release verdict remains **NO-GO** until the P0 findings
are closed and V1-05 records an explicit final decision.
