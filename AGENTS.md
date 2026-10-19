# AGENTS.md — PyScheduleKit

Single-package Python library (src layout, **zero runtime dependencies**, Python ≥3.11).
The only package is `src/pyschedulekit`; `tests/`, `scripts/`, `docs/` sit at the repo root.

## Commands

```bash
pip install -e ".[dev]"          # required: pre-commit hooks run system binaries
ruff check .                     # lint (covers tests/ and scripts/ too)
ruff format --check .            # `ruff format .` to fix
mypy src                         # strict mode; only src is type-checked, NOT tests
pytest                           # always run from the repo root (see gotcha below)
pytest tests/unit/domain/test_time_model.py::test_some_test   # single test
```

CI order (`.github/workflows/ci.yml`, Python 3.11/3.12/3.13):
`ruff check .` → `ruff format --check .` → `mypy src` → `pytest --cov=pyschedulekit`.

- `pre-commit` hooks (`.pre-commit-config.yaml`) are local + `language: system` and run
  each check against the **whole repo** (`pass_filenames: false`) — dev deps must be
  installed in the active environment or every hook fails.
- pytest is configured with `--strict-config --strict-markers` and `pythonpath = ["."]`
  (root on path so tests can `import scripts...`).

## Gotchas

- **Public API is a tested contract.** Changing any exported name requires updating all of:
  `src/pyschedulekit/api/_manifest.py` (`STABLE_PUBLIC_NAMES`, must stay sorted + unique),
  `src/pyschedulekit/api/__init__.py`, `src/pyschedulekit/__init__.py`.
  `tests/unit/api/test_public_api_contract.py` and V1 architecture tests enforce the exact
  63-name root, the complete 104-name `pyschedulekit.api` surface, object identity for root
  conveniences, API-only advanced names, and physical absence of the 11 removed legacy root
  redirects.
- **Version is asserted verbatim.** Single source: `src/pyschedulekit/_version.py`.
  `tests/test_package.py` hard-codes the version string and compares it to installed
  metadata — bumping the version means editing that test, and the package must be
  installed (`pip install -e .`) for `importlib.metadata` to resolve.
- **Architecture fitness tests fail the build** (`tests/architecture/test_domain_boundaries.py`):
  `domain/` must not import `application`, `infrastructure`, `ports`, `api`, or `runtime`,
  and must not call `datetime.now`/`date.today`/`time.sleep`/`os.getenv`. Time in the
  domain is always injected via a `Clock` port.
- **Release tests parse CI YAML with relative paths** (`WORKFLOW = Path(".github/workflows/...")`
  in `tests/unit/release/`) — pytest run from any other directory fails those tests.
  Editing `.github/workflows/release-*.yml` or `release-readiness.yml` can break them.
- Domain imports in tests are normal: tests may reach into `pyschedulekit.domain.*`
  and `pyschedulekit.application.*` directly; only the public surface is frozen.

## Architecture

Layered, domain-first (`domain` → `application` → `ports` → `infrastructure` → `api`):

- `domain/` — pure model (time, triggers, schedule, execution, policies). No I/O,
  no wall clock, no environment access.
- `application/` — orchestration services (scheduler engine, run_pending, recovery,
  outbox, retention, wakeup, …).
- `ports/` — interfaces (persistence, executor, clock, observability).
- `infrastructure/` — SQLite persistence (`sqlite_schema.py`), local/HTTP/routing
  executors, runtime loop.
- `api/` — the **complete stable** 104-name surface: `import pyschedulekit.api as psk`.
  The package root intentionally exposes only the 63 common convenience names.
- `experimental/` — explicitly outside the 1.x SemVer promise; the former 11 legacy root
  redirects were removed by V1-01.H.
- `testing/` — shipped helpers for consumers (`MutableClock`, `FixedClock`, test triggers);
  use these instead of sleeping or monkeypatching `datetime`.

## Specs and workflow

- Documentation entry point: `docs/README.md`.
- Current architecture: `docs/ARCHITECTURE.md`; current SDLC: `docs/SDLC.md`.
- Development is slice-based: `docs/implementation/LOT-*.md` (35 done, LOT-00…LOT-34),
  domain rationale in `docs/specs/`, release engineering in `docs/release/`.
- Project rule: *every supported guarantee must map to an executable test* — add the test
  alongside the behavior, and cover new guarantees in `tests/architecture` if they are
  structural.
- Commits use conventional format (`feat:`, `fix(release):`, `ci(release):`).
- Release tooling (only when touching releases): `python -m scripts.verify_distribution dist`,
  `python scripts/smoke_installed_package.py`, `python -m scripts.release_preflight`.

## Audit state

The full audit performed on 2026-10-08 is intentionally preserved as a historical snapshot.
Documentation entry point: `docs/README.md`. The dated audit snapshot lives under
`docs/audit/2026-10-08/`, including `CODEBASE_ANALYSIS.md`,
`ANALYSE_CRITIQUE.md`, and `RECOMMANDATIONS.md`.

**Do not treat the red states written inside those snapshot documents as current facts.**
The authoritative current disposition is:

`docs/audit/2026-10-08/POST_00_REMEDIATION_STATUS.md`

Current POST-00 state:

- B1–B12 have no remaining open finding.
- runtime transition races are regression-covered;
- SQLite bootstrap is qualified under concurrent initialization;
- admission-lock conflict recovery is covered;
- InMemory / SQLite persistence parity is enforced by shared tests;
- HTTP error-resource cleanup and redirects are hardened;
- failed implicit target registrations are compensated (B7);
- `coverage.report.fail_under = 85` is enforced;
- Ruff is pinned and GitHub Actions are SHA-pinned;
- CI and Distribution Qualification are mandatory on Python 3.11 / 3.12 / 3.13;
- `v0.1.0a3` exists as an immutable GitHub prerelease with wheel, sdist and checksum.

POST-00 is complete. The current development version is `0.1.0a4`.
Pre-1.0 milestones are **not published to PyPI**; the release workflow enforces public
publication only for stable semantic versions >= `1.0.0`.

POST-01 through POST-06 and PostgreSQL PG-00 → PG-05 are complete.
The 0.2.x PostgreSQL / Async Executor / ExecutorRegistry sequence is complete. The planned
0.3.x calendar sequence is also complete: CAL-00 Calendar Foundations ✅ → CAL-01 Schedule
Calendar Binding ✅ → CAL-02 Calendar-aware Occurrence Planning ✅ → CAL-03 Business-Day
Trigger Semantics ✅ → CAL-04 Persistence / Migration Parity ✅ → CAL-05 Calendar Provider
Adapters ✅. The 0.4.x composite-trigger sequence is complete: CMP-00 establishes the pure
temporal union contract, CMP-01 qualifies Schedule/Occurrence planning, CMP-02 bounds nested
unions plus recovery behavior, CMP-03 adds the shared versioned SQL definition codec, CMP-04
qualifies live InMemory/SQLite/PostgreSQL parity, and CMP-05 graduates `AnyOfTrigger` through
the stable API, public E2E, cookbook and benchmark surfaces. Calendars must remain
deterministic and versioned; do not couple
domain calendar rules to a holiday library, database, HTTP service, or global mutable
provider.
V1-00 readiness audit is complete and records a NO-GO for an immediate `v1.0.0`; the runtime
foundation is green. V1-01 has frozen the Python public contract and V1-02.A has frozen the
persistence read floors. Backup/rollback/operations persistence evidence, plus Python 3.14/warning/security gates and
stable-release workflow behavior, remain tracked in `docs/v1/`. V1-01.A Public API Inventory & Classification is complete:
`api/_manifest.py` now records the exact root/API, PostgreSQL, testing and experimental
surfaces plus their provisional V1 classifications, enforced by an architecture test.
V1-01.B Root/API Stable Candidate Review is complete: all 104 primary candidates remain
stable candidates in `pyschedulekit.api`, with 63 selected for the future compact root and
41 reserved for the advanced API-only surface. V1-01.C Secondary Namespace Policy is complete:
`postgres` is stable-optional, `testing` is stable-testing, `experimental` remains outside
SemVer, `__version__` has stable presence, and the 11 legacy root redirects must be removed
before `v1.0.0`. V1-01.D Constructor / Method Signature Freeze now records 39 consumer
constructors/factories and 53 public methods with executable name/kind/default snapshots.
V1-01.E Protocol / Enum / Exception Freeze now protects exported structural Protocols,
14 public Enum name/value sets and public exception catch categories, including the
non-exception diagnostic `*Error` records. V1-01.F Compatibility & Deprecation Policy is
complete: `docs/v1/V1-01F_COMPATIBILITY_DEPRECATION_POLICY.md` is the canonical 1.x
SemVer/typing/deprecation policy, with stable breaking changes reserved for the next major.
V1-01.G Executable Contract Snapshots is complete: 21 stable operation-result structures
have exact field/property snapshots in
`tests/architecture/test_v1_result_contract_snapshots.py`. V1-01.H Final Public Contract
Review is complete: the runtime now applies the 63-name compact root, retains all 104 stable
names in `pyschedulekit.api`, removes the 11 pre-1.0 root redirects, and marks the primary
contract frozen. V1-02.A Persistence Version Floor & Policy is complete: all currently
versioned persistence surfaces have a frozen 1.x read floor of v1, with current writer
versions centralized in `infrastructure/persistence_versions.py`. V1-02.B Immutable Golden
Compatibility Fixtures is complete: seven append-only JSON fixtures under
`tests/fixtures/persistence/v1/` are provenance- and SHA-256-protected, covering public
`v0.1.0a3` plus immutable pre-1.0 formats. V1-02.C SQLite Forward Migration Qualification
is complete: seven compressed physical SQLite fixtures cover schemas v1 through v7, with
compressed/raw hashes and full forward migration to v8 preserving durable state. V1-02.D
Codec Migration & Semantic Equivalence is complete: legacy ScheduleDefinition v1/v2 payloads
migrate to v3 without domain/occurrence drift, while SQL values, Trigger envelopes and
calendar codecs preserve behavioral semantics. V1-02.E PostgreSQL Evolution / Rolling Upgrade
is complete: schema-v1 same-contract overlap is live-qualified on PostgreSQL 16/17/18,
bootstrap is transaction-lock serialized, fencing takeover is monotonic, stale owners fail,
and arbitrary N/N+1 overlap requires explicit release-pair evidence. V1-02.F Backup /
Rollback / Operations Contract is next. Never regenerate or edit a merged golden or SQLite fixture to satisfy a new writer;
add a new versioned fixture instead. Do not bump the
version or create `v1.0.0` before V1-05.
PostgreSQL is public through `pyschedulekit.postgres`, supports PostgreSQL 16/17/18,
and must never break the base zero-runtime-dependency root import.
