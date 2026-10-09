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
  `tests/unit/api/test_public_api_contract.py` enforces exact `__all__` match, object
  identity between root and `pyschedulekit.api`, and legacy-name deprecation redirects.
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
- `api/` — the **stable** surface: `import pyschedulekit.api as psk`; the package root
  mirrors it for convenience.
- `experimental/` — no compatibility promise before 1.0; deprecated root names warn and
  redirect here.
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
The 0.2.x PostgreSQL / Async Executor / ExecutorRegistry sequence is complete. Current
sequence: 0.3.x CAL-00 Calendar Foundations ✅ → CAL-01 Schedule Calendar Binding ✅ →
CAL-02 Calendar-aware Occurrence Planning ✅ → CAL-03 Business-Day Trigger Semantics ✅ → CAL-04 Persistence / Migration Parity ✅ → CAL-05 Calendar Provider Adapters next. Calendars must remain deterministic and
versioned; do not couple domain calendar rules to a holiday
library, database, HTTP service, or global mutable provider.
PostgreSQL is public through `pyschedulekit.postgres`, supports PostgreSQL 16/17/18,
and must never break the base zero-runtime-dependency root import.
