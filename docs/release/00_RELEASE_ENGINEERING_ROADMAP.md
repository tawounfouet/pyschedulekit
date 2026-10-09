# PyScheduleKit — Release Engineering Roadmap

## Purpose

Release engineering is intentionally separated from scheduler-domain development.

The infrastructure was exercised publicly with `0.1.0a3`, then the project changed policy:
**no additional PyPI publication before the first stable `1.0.0` release**.

Pre-1.0 versions remain normal source-development milestones and continue to be validated by
CI, distribution builds and clean-install qualification.

## Current policy

```text
0.x source versions       → build / test / qualify only
1.0.0 alpha / beta / rc   → build / test / qualify only
stable >= 1.0.0           → public PyPI publication eligible
```

The executable publication guard lives in `scripts/release_policy.py` and is enforced by
`.github/workflows/release-candidate.yml`.

## Roadmap status

```text
RELEASE ENGINEERING & DISTRIBUTION
────────────────────────────────────────────────────────
REL-00  Distribution Contract                     ✅
REL-01  Wheel + sdist Build                        ✅
REL-02  Artifact / Metadata Validation             ✅
REL-03  Clean-Install Matrix                       ✅
REL-04  Version / Tag / Release Candidate Gate     ✅
REL-05  TestPyPI Trusted Publishing                ✅ historical / optional
REL-06  PyPI Trusted Publishing                    ✅ proven / dormant until 1.0.0
REL-07  GitHub Release + Provenance                ✅ proven on 0.1.0a3
REL-08  Release Runbook / Rollback Discipline      ✅

PRE-1.0 PUBLICATION
────────────────────────────────────────────────────────
PyPI publication                                  ⛔ intentionally disabled
Public release ceremony                           ⛔ not required
Normal CI / distribution qualification            ✅ mandatory

NEXT PUBLIC RELEASE TARGET
────────────────────────────────────────────────────────
1.0.0 stable                                      ⬜ future
```

## Release invariants

Every candidate intended for eventual public release must preserve these properties:

1. the source tree passes the normal CI quality matrix;
2. `python -m build` produces exactly one wheel and one source distribution;
3. the wheel is pure Python: `py3-none-any`;
4. wheel and sdist versions equal `pyschedulekit.__version__`;
5. metadata declares `Requires-Python >=3.11`;
6. the PEP 561 `py.typed` marker ships in both distribution formats;
7. `twine check --strict` accepts every artifact;
8. wheel and sdist install successfully in clean environments;
9. installed-package smoke tests run outside the repository source tree;
10. public publication uses short-lived GitHub OIDC rather than a long-lived PyPI token.

These invariants remain useful before `1.0.0` even when no package is uploaded.

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
clean-install matrix
      │
      ├── Python 3.11 ─ wheel + sdist
      ├── Python 3.12 ─ wheel + sdist
      └── Python 3.13 ─ wheel + sdist
      │
      ▼
installed-package smoke test
```

This is the default pre-1.0 path.

## Public publication path

The public path is dormant before stable `1.0.0`:

```text
stable source version >= 1.0.0
      ↓
Release Readiness
      ↓
tag vX.Y.Z
      ↓
qualify exact artifacts
      ↓
build provenance
      ↓
PyPI Trusted Publishing
      ↓
verify installation from pypi.org
      ↓
GitHub Release + checksum/provenance verification
```

The exact qualified wheel/sdist must be reused downstream; publication jobs never rebuild
new bytes.

## Security model

Public publication uses GitHub OIDC / PyPI Trusted Publishing.

```text
GitHub Actions
      │
      │ short-lived OIDC identity
      ▼
PyPI
      │
      ▼
temporary upload credential
```

No permanent PyPI API token is required in repository secrets.

The historical TestPyPI path remains useful for experiments but is not a required production
stage.

## Proven public reference

The last public prerelease remains `0.1.0a3`.

It demonstrated:

- PyPI Trusted Publishing;
- exact artifact reuse;
- GitHub build attestations;
- immutable GitHub prerelease assets;
- wheel/sdist/checksum verification.

Later development versions do not need corresponding PyPI or GitHub releases.

## Before 1.0.0

The project should spend the pre-1.0 period on framework maturity:

```text
POST-01 documentation cleanup
POST-02 real-world examples / cookbook
POST-03 API documentation
POST-04 dogfooding
POST-05 benchmarks
POST-06 chaos / fault injection
0.2.x+ execution and storage evolution
...
1.0 compatibility / migration / security qualification
```

No public package publication is required to progress through those milestones.

## 1.0.0 activation gate

Before creating `v1.0.0`, all of the following must be true:

- source version and changelog are `1.0.0`;
- CI and distribution qualification are green;
- compatibility and migration policy are finalized;
- the public API contract is stable;
- release workflow behavior for a stable GitHub Release has been qualified;
- PyPI Trusted Publisher identity is still valid;
- GitHub Immutable Releases / provenance controls are valid;
- Release Readiness passes on `main`.

Only then is the public pipeline reactivated.

## Operating rule

```text
before 1.0.0:
    develop → test → qualify → merge

at/after stable 1.0.0:
    develop → test → qualify → readiness → tag → publish → verify
```

This keeps release ceremony proportional to the maturity promise being made.
