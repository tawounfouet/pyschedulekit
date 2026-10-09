# REL-08 — Release Runbook / Rollback Discipline

## Status

This runbook describes the **current production release path** for PyScheduleKit.

The first public go-live was completed with `0.1.0a3`. The next release prepared by this
runbook is:

```text
PyScheduleKit 1.0.0
tag: v1.0.0
theme: first stable public contract
```

Historical TestPyPI work remains documented in REL-05 and the changelog, but **TestPyPI is
not a mandatory stage of the production pipeline**.

No `0.x`, alpha, beta or release-candidate build is published to PyPI anymore. Pre-1.0
versions are development milestones validated through normal CI and distribution
qualification. The public release pipeline is intentionally dormant until stable `1.0.0`.

## Release pipeline

The tagged production path is:

```text
tag v<version>
      ↓
qualify-release-candidate
      ↓
build wheel + sdist once
      ↓
metadata / distribution / version identity checks
      ↓
GitHub build provenance
      ↓
publish-pypi
      ↓
verify-pypi from canonical index
      ↓
create-github-release
      ↓
verify-github-release + checksums + provenance
```

Artifacts are built once during qualification and reused downstream. Publication jobs must
never rebuild different bytes.

## Core release principle

Release state falls into two classes.

### Re-runnable state

```text
Release Readiness
build before publication
metadata validation
distribution qualification
tag/source/artifact identity checks
network verification
post-publish smoke verification
```

A transient failure can be retried only when the source commit, release identity and
artifact bytes remain unchanged.

### Irreversible public state

```text
PyPI accepted version/files
immutable GitHub Release
```

Once PyPI accepts a distribution filename/version, that release identity is consumed.
Once an immutable GitHub Release exists, its tag/assets are permanent evidence.

The recovery rule is:

```text
correct artifact + transient infrastructure failure
              ↓
       rerun smallest failed job

artifact/code/metadata must change
              ↓
      never replace published bytes
              ↓
          increment version
              ↓
            fix forward
```

## Release Readiness

Before creating a release tag, run:

```text
.github/workflows/release-readiness.yml
```

from `main` with:

```text
release_tag = v1.0.0
PyPI Trusted Publisher ready = true
Immutable Releases ready     = true
```

The readiness workflow **never creates or pushes a tag**.

It proves:

1. execution is from `main`;
2. the requested tag is unused;
3. tag version equals `pyschedulekit.__version__`;
4. `CHANGELOG.md` contains a dated heading for that version;
5. PyPI Trusted Publishing and GitHub Immutable Releases are explicitly acknowledged;
6. wheel and sdist build correctly;
7. Twine validates package metadata and README rendering;
8. the distribution contract passes;
9. the release-candidate identity gate passes.

## External controls

### PyPI

```text
Project       pyschedulekit
Owner         tawounfouet
Repository    pyschedulekit
Workflow      release-candidate.yml
Environment   pypi
Authentication GitHub OIDC / Trusted Publishing
```

No long-lived PyPI token belongs in repository or environment secrets for this flow.

### GitHub

```text
Immutable Releases enabled
Build attestations enabled through workflow permissions
```

TestPyPI may be used manually for experiments, but it is not a release gate.

## GO / NO-GO checklist for 1.0.0

```text
SOURCE
[ ] main contains the exact intended release commit
[ ] CI green on Python 3.11 / 3.12 / 3.13
[ ] Distribution Qualification green
[ ] package version is 1.0.0
[ ] CHANGELOG.md contains a dated `## [1.0.0] - YYYY-MM-DD` section
[ ] no release-affecting changes are pending

IDENTITY
[ ] v1.0.0 does not already exist
[ ] release tag exactly matches package version

PYPI
[ ] GitHub environment pypi exists
[ ] PyPI Trusted Publisher identity matches repository/workflow/environment

GITHUB
[ ] Immutable Releases enabled
[ ] release-candidate workflow is present on the commit to tag
[ ] provenance permissions/actions are present and SHA-pinned
[ ] GitHub Release creation is configured as a stable release, not a prerelease

READINESS
[ ] Release Readiness passed on main for v1.0.0
```

Any unchecked item is **NO-GO**.

## Go-live procedure

### 1. Synchronize main

```bash
git fetch origin main
git switch main
git pull --ff-only origin main
```

Never release from a feature branch or detached commit.

### 2. Confirm package version

```bash
python -c "import pyschedulekit; print(pyschedulekit.__version__)"
```

Expected for this release:

```text
1.0.0
```

### 3. Run Release Readiness

Run the manual workflow on `main` with `release_tag=v1.0.0` and both external-control
acknowledgements enabled.

Do not tag until this run is green.

### 4. Create one annotated tag

```bash
git tag -a v1.0.0 -m "PyScheduleKit v1.0.0"
```

Signing the annotated tag is recommended when local signing is configured.

### 5. Push only that tag

```bash
git push origin v1.0.0
```

This starts the Release Candidate Gate.

Never move or replace the tag if a downstream job fails.

> **Stable-release prerequisite:** the current release infrastructure was proven using
> prerelease `0.1.0a3`. Before `v1.0.0`, the GitHub Release creation step must be
> qualified in stable-release mode (`isPrerelease=false`). This is a GO/NO-GO item, not
> something to discover after PyPI publication.

## Expected workflow order

```text
1. qualify-release-candidate
       ↓
2. publish-pypi
       ↓
3. verify-pypi
       ↓
4. create-github-release
       ↓
5. verify-github-release
```

No downstream stage should be manually bypassed.

## Success criteria

A release is complete only when all are true:

```text
[ ] candidate tag/source/artifact version identity passed
[ ] wheel + sdist metadata/distribution checks passed
[ ] GitHub build provenance exists
[ ] exact qualified artifacts published to PyPI
[ ] exact version can be installed from pypi.org
[ ] installed-package smoke test passes outside the source tree
[ ] stable GitHub Release created from the existing tag
[ ] wheel, sdist and release-candidate-sha256.txt attached
[ ] published assets re-downloaded and checksum-verified
[ ] GitHub attestations verify
[ ] immutable release verification succeeds
```

## Failure and recovery matrix

| Failure point | Public state | Recovery |
|---|---|---|
| readiness / before tag | none | fix `main`, rerun readiness |
| qualification before PyPI | tag exists, no public package | transient failure: rerun; code/artifact change: bump version + new tag |
| PyPI upload fails before acceptance | no accepted package for candidate | repair OIDC/service issue and rerun exact artifact job |
| PyPI succeeds, verification fails transiently | PyPI version consumed | rerun verification only |
| published PyPI artifact is defective | production version consumed | yank if appropriate, fix on main, bump version, new tag |
| GitHub Release creation fails | package already on PyPI | rerun release job with retained exact artifacts |
| GitHub verification fails transiently | release may already exist | rerun verification only |
| immutable Release contains defective release identity | permanent tag/assets | preserve evidence, yank PyPI if needed, bump version, fix forward |

## Retry discipline

Retry is allowed only when all of these remain identical:

```text
source commit
release tag
package version
wheel bytes
sdist bytes
checksum manifest
```

Examples of retryable failures:

- temporary PyPI outage;
- index propagation delay;
- temporary GitHub outage;
- smoke-test network failure;
- post-release verification timeout.

Do **not**:

- move or force-push a release tag;
- rebuild changed bytes under the same version;
- delete/re-upload an existing PyPI filename;
- replace immutable GitHub Release assets.

If code or artifact bytes must change, increment the version.

## PyPI rollback policy

PyPI does not provide byte-level rollback for an already published version.

For a defective public package:

```text
detect
  ↓
yank affected version when appropriate
  ↓
document reason
  ↓
fix main
  ↓
increment version
  ↓
run full readiness and release pipeline again
```

A yanked version remains installable when explicitly pinned, preserving reproducibility.

## Immutable GitHub Release recovery

With Immutable Releases enabled:

- release identity is permanent;
- the release tag must not be moved;
- release assets must not be replaced;
- a corrected build requires a new package version and tag.

Release notes may be amended to warn users and point to the fixed version.

## Security incident

If a release is suspected to be compromised:

1. stop remaining downstream jobs where possible;
2. yank the affected PyPI release when appropriate;
3. preserve workflow runs, checksums, attestations and commit SHA;
4. investigate repository / Trusted Publisher compromise;
5. rotate credentials only if a credential was actually exposed;
6. fix on `main`;
7. increment version;
8. run Release Readiness again;
9. publish a new immutable release.

Never hide an incident by replacing bytes under the same identity.

## Changelog discipline

Before tagging, freeze release notes under a dated heading using the actual release date:

```text
## [1.0.0] - YYYY-MM-DD
```

Future changes remain under:

```text
## [Unreleased]
```

The preflight enforces that the candidate package version has a dated changelog heading.

## Post-release verification

After the workflow is fully green:

```bash
python -m pip install --upgrade pyschedulekit==1.0.0
python -c "import pyschedulekit; print(pyschedulekit.__version__)"
```

Expected:

```text
1.0.0
```

Verify provenance for a downloaded wheel:

```bash
gh attestation verify \
  pyschedulekit-1.0.0-py3-none-any.whl \
  --repo tawounfouet/pyschedulekit
```

Verify the GitHub Release:

```bash
gh release verify v1.0.0
```

## Release record to retain

```text
version
tag
commit SHA
Release Readiness run
Release Candidate Gate run
wheel filename
sdist filename
release-candidate-sha256.txt
PyPI project/version URL
GitHub Release URL
build attestations
immutable-release verification
incident notes, if any
```

## Release engineering status

```text
REL-00  Distribution Contract                     ✅
REL-01  Wheel + sdist Build                        ✅
REL-02  Artifact / Metadata Validation             ✅
REL-03  Clean-Install Matrix                       ✅
REL-04  Version / Tag / Release Candidate Gate     ✅
REL-05  TestPyPI Trusted Publishing                ✅ implemented / historical
REL-06  PyPI Trusted Publishing                    ✅ available / deferred to stable 1.0.0
REL-07  GitHub Release + Provenance                ✅ available
REL-08  Release Runbook / Rollback Discipline      ✅
```

The release-engineering implementation is operational but deliberately dormant during
pre-1.0 development. Resume this runbook only when the source version reaches stable
`1.0.0`; then run Release Readiness on `main` before creating `v1.0.0`.
