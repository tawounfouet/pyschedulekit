# V1-03.A — Python 3.14 & Support Window

**Scope:** supported CPython minor versions for the PyScheduleKit 1.x line.

**Runtime behavior changed:** no  
**Package version changed:** no  
**Publication state changed:** no

## Objective

The V1-00 readiness audit found that PyScheduleKit passed locally on Python 3.14 but only
declared/qualified Python 3.11 through 3.13.

V1-03.A closes that gap by making the support window explicit and executable.

## Stable 1.x support window

```text
Python 3.11
Python 3.12
Python 3.13
Python 3.14
```

Package metadata therefore declares:

```text
Requires-Python: >=3.11,<3.15
```

The upper bound is deliberate.

PyScheduleKit does not claim support for a future Python minor before that interpreter has
passed the project's qualification gates.

## Why an explicit upper bound

Before V1-03.A the project used `>=3.11` while CI only covered through 3.13.

That allowed an unqualified future interpreter to install the package even though the stable
support promise had never been tested there.

The 1.x policy is now:

```text
installable minor == qualified minor
```

A future Python 3.15 enablement requires a normal source change that:

1. extends `Requires-Python`;
2. adds the classifier;
3. adds 3.15 to CI;
4. adds 3.15 to wheel/sdist clean-install qualification;
5. closes warning/runtime regressions found by the new interpreter.

## Machine-readable source

`pyproject.toml` contains:

```toml
[tool.pyschedulekit.platform]
supported-python-minors = ["3.11", "3.12", "3.13", "3.14"]
newest-supported-python = "3.14"
```

The project metadata and CI matrices are checked against this contract by:

`tests/architecture/test_v1_python_support_window.py`

## CI qualification

The normal quality workflow runs on every supported Python minor:

```text
3.11  Ruff / format / mypy / pytest
3.12  Ruff / format / mypy / pytest
3.13  Ruff / format / mypy / pytest
3.14  Ruff / format / mypy / pytest
```

V1-03.A only proves functional/platform compatibility.

Warning cleanliness on the newest supported interpreter is intentionally a separate gate in
V1-03.B.

## Distribution qualification

Wheel and source-distribution clean-install qualification runs for:

```text
             wheel   sdist
Python 3.11    ✅      ✅
Python 3.12    ✅      ✅
Python 3.13    ✅      ✅
Python 3.14    ✅      ✅
```

Every entry still performs:

- installation from the built artifact;
- `pip check`;
- installed-package smoke test outside the source tree;
- external-consumer dogfood.

The distribution verifier now requires the exact metadata contract:

```text
Requires-Python >=3.11,<3.15
```

## Optional adapters

The base Python support promise applies to the public PyScheduleKit package.

Optional integrations remain subject to their own dependency/platform qualification. The
PostgreSQL adapter continues to be live-qualified independently against PostgreSQL 16/17/18.

## Readiness finding closure

V1-03.A closes:

```text
V1-F06 — Python 3.14 is not in the declared qualification matrix
```

Closure evidence:

- Python 3.14 classifier;
- explicit `>=3.11,<3.15` metadata;
- four-minor CI matrix;
- four-minor wheel/sdist matrix;
- executable support-window architecture test.

## V1-03 delivery sequence

```text
V1-03.A  Python 3.14 & Support Window               COMPLETE
V1-03.B  Warning-Clean Runtime / Tests              NEXT
V1-03.C  Dependency Vulnerability Gate              PLANNED
V1-03.D  GitHub Actions / Runner Deprecation Gate   PLANNED
V1-03.E  Final Platform & Security Review           PLANNED
```

## Deliberate boundary

V1-03.A does not:

- close SQLite ResourceWarning findings;
- add dependency vulnerability scanning;
- change GitHub Actions/runner policy;
- bump the package version;
- create a tag;
- publish anything.

Those remain V1-03.B through V1-03.E.

---

**Status:** V1-03.A complete once CI and Distribution Qualification are green on Python
3.11/3.12/3.13/3.14. Next: **V1-03.B — Warning-Clean Runtime / Tests**.
