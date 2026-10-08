# REL-00 → REL-03 — Distribution Qualification

## Scope

This increment establishes the packaging qualification boundary for PyScheduleKit `0.1.0a1`.

It does not publish to TestPyPI or PyPI yet.

## Release tooling

The project exposes a dedicated optional dependency group:

```bash
python -m pip install -e ".[release]"
```

It installs the tools required to build and validate uploadable distributions:

- `build`
- `twine`

These dependencies are release-engineering tools and are not runtime dependencies of PyScheduleKit.

## Build

The canonical build command is:

```bash
python -m build
```

It must generate:

```text
dist/
├── pyschedulekit-0.1.0a1-py3-none-any.whl
└── pyschedulekit-0.1.0a1.tar.gz
```

The CI build exports `SOURCE_DATE_EPOCH` from the Git commit timestamp before invoking the build backend, reducing avoidable timestamp variability in artifacts.

## Metadata validation

Every distribution is checked with:

```bash
python -m twine check --strict dist/*
```

This validates package metadata and the long-description rendering that PyPI will consume.

## Distribution contract verifier

`scripts/verify_distribution.py` validates artifact-level invariants that ordinary unit tests do not cover.

For the wheel it checks:

- exactly one wheel exists;
- canonical versioned filename;
- pure-Python `py3-none-any` compatibility tag;
- `pyschedulekit/__init__.py` is present;
- `pyschedulekit/_version.py` is present;
- `pyschedulekit/py.typed` is present;
- metadata name is `pyschedulekit`;
- metadata version matches the runtime version;
- `Requires-Python` is exactly `>=3.11`.

For the sdist it checks:

- exactly one `.tar.gz` exists;
- canonical versioned filename;
- one canonical top-level directory;
- `LICENSE`, `README.md`, and `pyproject.toml` are included;
- package source files are included;
- the PEP 561 marker is included.

## Clean-install qualification

The distribution workflow stores the built distributions as one GitHub Actions artifact.

A second job downloads those exact bytes and tests this matrix:

```text
              wheel   sdist
Python 3.11     ✅      ✅
Python 3.12     ✅      ✅
Python 3.13     ✅      ✅
```

Each matrix entry performs:

```text
pip install <built artifact>
      ↓
pip check
      ↓
run smoke test from /tmp
```

Running the smoke test from `/tmp` prevents the repository checkout from accidentally shadowing the installed package.

## Installed-package smoke contract

`scripts/smoke_installed_package.py` verifies:

- distribution metadata version equals `pyschedulekit.__version__`;
- expected release version is `0.1.0a1`;
- root and canonical API exports resolve to the same objects;
- stable exports remain public;
- experimental coordination primitives are not in `__all__`;
- `py.typed` is installed;
- a default `Scheduler` can be constructed;
- its persistence health probe succeeds.

## CI workflow

The qualification workflow is:

```text
.github/workflows/distribution.yml
```

It runs on:

- pull requests;
- pushes to `main`;
- manual `workflow_dispatch`.

This makes packaging regressions first-class CI failures rather than release-day surprises.

## Definition of done

REL-00 through REL-03 are complete when both workflows are green:

```text
CI
Distribution Qualification
```

and all six clean-install matrix entries pass from the same built artifact set.
