# REL-04 — Version / Tag / Release Candidate Gate

## Goal

Prevent a Git release tag from ever qualifying or publishing artifacts whose package version differs from the tag.

The release identity invariant is:

```text
Git tag
   ==
source package version
   ==
wheel metadata version
   ==
sdist version
```

For PyScheduleKit `0.1.0a1`, the only canonical release tag is:

```text
v0.1.0a1
```

## Canonical tag format

The gate requires an explicit `v` prefix:

```text
v<package-version>
```

Examples:

```text
v0.1.0a1   ✅
0.1.0a1    ❌
v          ❌
 v0.1.0a1  ❌
v0.1.0a1   ❌  when source version is 0.1.0a2
```

No normalization silently changes the requested release identity. The version after `v` must equal the package version exactly.

## Release-candidate verifier

The repository provides:

```text
scripts/verify_release_candidate.py
```

Canonical invocation:

```bash
python -m scripts.verify_release_candidate \
  --release-tag v0.1.0a1 \
  dist
```

The verifier first checks tag/source equality. A mismatch fails before artifact qualification.

If versions match, it delegates to the existing distribution contract, which verifies the wheel and sdist against the source package version.

## Why mismatch fails before artifact inspection

A tag mismatch is a release-identity failure, not an artifact-detail failure.

The order is therefore:

```text
release tag
    ↓
compare with source version
    │
    ├── mismatch → FAIL immediately
    │
    └── match
          ↓
      validate wheel/sdist
```

This prevents an incorrectly tagged release from consuming or publishing artifacts merely because those artifacts are internally coherent.

## Tagged release workflow

The release-candidate workflow is:

```text
.github/workflows/release-candidate.yml
```

It triggers on:

```yaml
push:
  tags:
    - "v*"
```

and also supports manual dry-run qualification through `workflow_dispatch`.

## Main-line ancestry

For real tag-push runs, the tagged commit must be reachable from `main`.

Conceptually:

```text
tag commit
    │
    └── ancestor of origin/main ? ── no → FAIL
                                 └─ yes → continue
```

This blocks accidental releases from abandoned feature branches or detached experimental commits.

## Candidate build

The workflow uses the same distribution discipline established in REL-01:

```text
tagged commit
     ↓
SOURCE_DATE_EPOCH = commit timestamp
     ↓
python -m build
     ↓
wheel + sdist
```

The artifacts then pass:

1. `twine check --strict`;
2. distribution contract verification;
3. tag/source/artifact identity verification;
4. SHA-256 checksum recording.

## Qualified candidate artifact

A successful run uploads:

```text
release-candidate-dists-<tag>
```

containing:

```text
dist/
├── pyschedulekit-<version>-py3-none-any.whl
└── pyschedulekit-<version>.tar.gz

release-candidate-sha256.txt
```

Retention is 30 days.

This artifact becomes the hand-off point for REL-05 and REL-06.

## Build once rule

Publication jobs must consume the candidate artifact produced by the same release workflow.

They must not run `python -m build` again.

Target flow:

```text
TAG
 ↓
BUILD ONCE
 ↓
QUALIFY
 ↓
RELEASE CANDIDATE ARTIFACT
 ├──→ TestPyPI
 └──→ PyPI
```

## Pull-request qualification

A real tag workflow cannot run on every pull request.

Therefore `Distribution Qualification` performs a dry-run gate using the source version converted to its canonical `v<version>` tag form.

This proves that:

- the module imports correctly;
- the CLI executes correctly;
- the built artifacts satisfy the release gate;
- release-gate changes participate in normal pull-request CI.

Negative mismatch scenarios are covered by unit tests.

## Tests

REL-04 qualifies:

- canonical `v`-prefixed tag acceptance;
- missing-prefix rejection;
- empty-version rejection;
- surrounding-whitespace rejection;
- tag/source mismatch rejection;
- fail-before-artifact-validation semantics;
- successful delegation to distribution qualification.

## Important release discipline

REL-04 does **not** create the actual `v0.1.0a1` Git tag yet.

The tag should only be created once the tagged commit already contains the intended publication workflow.

Otherwise the immutable release tag would point to a commit that cannot execute the final release process.

## Roadmap

```text
RELEASE ENGINEERING & DISTRIBUTION
────────────────────────────────────────────────────────
REL-00  Distribution Contract                     ✅
REL-01  Wheel + sdist Build                        ✅
REL-02  Artifact / Metadata Validation             ✅
REL-03  Clean-Install Matrix                       ✅
REL-04  Version / Tag / Release Candidate Gate     ✅
REL-05  TestPyPI Trusted Publishing               ⏭ NEXT
REL-06  PyPI Trusted Publishing                    ⬜
REL-07  GitHub Release + Provenance                ⬜
REL-08  Release Runbook / Rollback Discipline      ⬜
```

## Next

`REL-05 — TestPyPI Trusted Publishing`
