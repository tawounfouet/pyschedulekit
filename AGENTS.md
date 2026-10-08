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

- Development is slice-based: `docs/implementation/LOT-*.md` (35 done, LOT-00…LOT-34),
  domain rationale in `docs/specs/`, release engineering in `docs/release/`.
- Project rule: *every supported guarantee must map to an executable test* — add the test
  alongside the behavior, and cover new guarantees in `tests/architecture` if they are
  structural.
- Commits use conventional format (`feat:`, `fix(release):`, `ci(release):`).
- Release tooling (only when touching releases): `python -m scripts.verify_distribution dist`,
  `python scripts/smoke_installed_package.py`, `python -m scripts.release_preflight`.

## Audit state (2026-10-08)

A full codebase audit sits at the repo root (in French). Entry point: `INDEX.md`;
remediation plan: `RECOMMANDATIONS.md` (bugs **B1–B12**, phased fixes);
verified facts: `CODEBASE_ANALYSIS.md`. Known red states until those fixes land:

- `ruff format --check .` **fails** on `scripts/release_preflight.py:27` — CI is red
  on `main` (bug B3); `ruff format scripts/release_preflight.py` is the fix.
- `docs/specs/` (26 files) is **not git-tracked**; run `ruff format docs/specs` before
  the first `git add docs/specs` or CI will fail on them (bug B12).
- The `v0.1.0a3` GitHub Release is missing (PyPI is published): the
  `create-github-release` job lacks `actions/checkout` (bug B4).
