# PyScheduleKit — Release Engineering Roadmap

## Purpose

The initial functional roadmap ends at LOT-34. Release engineering is tracked separately so packaging, publication, provenance, and operational release discipline do not get confused with scheduler-domain features.

The target release is:

```text
PyScheduleKit 0.1.0a1
```

## Roadmap

```text
RELEASE ENGINEERING & DISTRIBUTION
────────────────────────────────────────────────────────
REL-00  Distribution Contract                     ✅
REL-01  Wheel + sdist Build                        ✅
REL-02  Artifact / Metadata Validation             ✅
REL-03  Clean-Install Matrix                       ✅
REL-04  Version / Tag / Release Candidate Gate     ⏭ NEXT
REL-05  TestPyPI Trusted Publishing                ⬜
REL-06  PyPI Trusted Publishing                    ⬜
REL-07  GitHub Release + Provenance                ⬜
REL-08  Release Runbook / Rollback Discipline      ⬜
```

## Release invariants

Every releasable commit must satisfy the following properties:

1. the source tree passes the normal CI quality matrix;
2. `python -m build` produces exactly one wheel and one source distribution;
3. the wheel is a pure-Python `py3-none-any` wheel;
4. wheel and sdist versions equal `pyschedulekit.__version__`;
5. wheel metadata declares `Requires-Python >=3.11`;
6. the PEP 561 `py.typed` marker ships in both distribution formats;
7. `twine check --strict` accepts every uploadable artifact;
8. wheel and sdist install successfully in clean environments;
9. installed-package smoke tests run outside the repository source tree;
10. publication never depends on long-lived PyPI credentials stored in GitHub Secrets.

## Security model

Publication will use PyPI Trusted Publishing through GitHub OIDC.

```text
GitHub Actions
      │
      │ short-lived OIDC identity
      ▼
PyPI / TestPyPI
      │
      ▼
temporary upload credential
```

No permanent PyPI API token is required in the repository configuration.

Dedicated GitHub environments will be used for publication gates:

```text
testpypi
pypi
```

Production publication will remain separated from ordinary pull-request CI.

## Current qualification flow

```text
source checkout
      │
      ▼
python -m build
      │
      ├── pyschedulekit-<version>-py3-none-any.whl
      └── pyschedulekit-<version>.tar.gz
      │
      ▼
twine check --strict
      │
      ▼
distribution contract verification
      │
      ▼
GitHub Actions artifact
      │
      ├── Python 3.11 ─ wheel + sdist clean install
      ├── Python 3.12 ─ wheel + sdist clean install
      └── Python 3.13 ─ wheel + sdist clean install
      │
      ▼
installed-package smoke test
```

## Why build once

The publication artifact must be the same artifact that was qualified.

The release pipeline therefore follows:

```text
BUILD ONCE
   ↓
QUALIFY
   ↓
STORE AS CI ARTIFACT
   ↓
PUBLISH THAT ARTIFACT
```

A later publication job must not rebuild the package independently, because doing so would publish bytes that were not the exact bytes previously qualified.

## Next milestone

REL-04 will introduce an explicit release-candidate gate:

```text
package version
      ==
release tag version
      ==
artifact metadata version
```

Only after that invariant is executable will TestPyPI publication be enabled.
