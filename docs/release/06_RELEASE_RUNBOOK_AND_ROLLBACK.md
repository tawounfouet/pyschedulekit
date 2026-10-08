# REL-08 — Release Runbook / Rollback Discipline

## Goal

Turn the PyScheduleKit release chain into an operator-safe procedure for the first real release and every subsequent release.

REL-08 defines:

- pre-release readiness;
- go/no-go conditions;
- exact tag procedure;
- workflow monitoring order;
- success criteria;
- transient-failure rerun rules;
- irreversible-publication rules;
- yank/fix-forward policy;
- GitHub immutable-release recovery;
- post-release verification.

The target first release remains:

```text
PyScheduleKit 0.1.0a1
tag: v0.1.0a1
```

## Core principle

A release has two classes of state.

### Re-runnable state

```text
CI
build
metadata validation
distribution qualification
index verification
release verification
```

A transient failure in these steps can usually be retried without changing the release identity.

### Irreversible public state

```text
TestPyPI upload
PyPI upload
immutable GitHub Release
```

Once a distribution filename/version has been published, the release must be treated as consumed.

The recovery model is:

```text
artifact correct + infrastructure failure
              ↓
        rerun failed step

artifact incorrect / code fix required
              ↓
        DO NOT replace bytes
              ↓
     increment package version
              ↓
          fix forward
```

## Release-readiness workflow

Before creating any real release tag, run:

```text
.github/workflows/release-readiness.yml
```

from:

```text
main
```

with:

```text
release_tag = v0.1.0a1

TestPyPI Trusted Publisher ready = true
PyPI Trusted Publisher ready     = true
Immutable Releases ready         = true
```

This workflow never creates or pushes a Git tag.

It proves:

1. it is running from `main`;
2. the requested tag does not already exist;
3. tag version equals `pyschedulekit.__version__`;
4. the changelog has a dated release heading;
5. all external release controls are explicitly acknowledged;
6. wheel and sdist build correctly;
7. Twine accepts the distributions;
8. distribution contract passes;
9. release-candidate identity gate passes.

## External controls

The readiness workflow requires acknowledgement of controls that cannot safely be inferred from ordinary repository CI permissions.

### TestPyPI

```text
Project           pyschedulekit
Owner             tawounfouet
Repository        pyschedulekit
Workflow          release-candidate.yml
Environment       testpypi
```

### PyPI

```text
Project           pyschedulekit
Owner             tawounfouet
Repository        pyschedulekit
Workflow          release-candidate.yml
Environment       pypi
```

### GitHub

```text
Immutable Releases enabled
```

The two GitHub environments should contain no long-lived package-index credentials.

## Go / no-go checklist

The release is GO only when every item is true.

```text
SOURCE
[ ] main contains the intended release commit
[ ] CI is green on Python 3.11 / 3.12 / 3.13
[ ] Distribution Qualification is green
[ ] package version is 0.1.0a1
[ ] CHANGELOG.md contains the dated 0.1.0a1 section
[ ] no additional code changes are pending

IDENTITY
[ ] v0.1.0a1 does not already exist
[ ] release tag exactly matches package version

TESTPYPI
[ ] GitHub environment testpypi exists
[ ] TestPyPI Trusted Publisher identity is correct

PYPI
[ ] GitHub environment pypi exists
[ ] PyPI Trusted Publisher identity is correct

GITHUB
[ ] Immutable Releases is enabled
[ ] release workflow exists on the commit to be tagged
[ ] release provenance workflow exists on the commit to be tagged

READINESS
[ ] Release Readiness workflow passed on main
```

Any unchecked item is NO-GO.

## First release procedure

### Step 1 — synchronize local main

```bash
git fetch origin main
git switch main
git pull --ff-only origin main
```

Do not release from a feature branch or detached commit.

### Step 2 — confirm version

```bash
python -c "import pyschedulekit; print(pyschedulekit.__version__)"
```

Expected:

```text
0.1.0a1
```

### Step 3 — create one annotated release tag

```bash
git tag -a v0.1.0a1 -m "PyScheduleKit v0.1.0a1"
```

If local Git tag signing is configured, signing the annotated tag is recommended.

### Step 4 — push only the release tag

```bash
git push origin v0.1.0a1
```

This starts:

```text
Release Candidate Gate
```

Do not push a replacement tag if the workflow later fails.

## Expected workflow order

```text
1. qualify-release-candidate
       ↓
2. publish-testpypi
       ↓
3. verify-testpypi
       ↓
4. publish-pypi
       ↓
5. verify-pypi
       ↓
6. create-github-release
       ↓
7. verify-github-release
```

A downstream stage must not be manually bypassed.

## Success criteria

A release is complete only when all of the following are true:

```text
[ ] release-candidate version gate passed
[ ] GitHub build provenance created
[ ] TestPyPI upload succeeded
[ ] TestPyPI reinstall succeeded
[ ] TestPyPI smoke test succeeded
[ ] PyPI upload succeeded
[ ] PyPI reinstall succeeded
[ ] PyPI smoke test succeeded
[ ] GitHub prerelease created
[ ] GitHub release assets re-downloaded
[ ] release SHA-256 manifest verified
[ ] GitHub artifact provenance verified
[ ] immutable release verification succeeds
```

## Failure and recovery matrix

| Failure point | Public state | Recovery |
| --- | --- | --- |
| readiness / before tag | none | fix `main`, rerun readiness |
| qualification before any upload | tag exists, no index upload | transient: rerun failed job; code fix: bump version and create a new tag |
| TestPyPI upload fails before acceptance | no accepted artifact | correct external config or transient issue, rerun failed job |
| TestPyPI upload succeeds, verification fails transiently | TestPyPI version consumed | rerun verification only |
| TestPyPI artifact is wrong | TestPyPI version consumed | never overwrite; fix code, bump version, new tag |
| PyPI upload fails before acceptance | TestPyPI consumed, PyPI not | repair PyPI/OIDC issue; rerun PyPI job only |
| PyPI upload succeeds, verification fails transiently | production version consumed | rerun verification only |
| PyPI artifact is wrong | production version consumed | yank affected PyPI release, fix code, bump version, publish new release |
| GitHub Release creation fails | package already on PyPI | rerun GitHub Release job using retained exact artifact |
| GitHub Release verification fails transiently | release may exist | rerun verification only |
| immutable GitHub Release has bad artifact | tag/assets immutable | do not replace; yank bad PyPI release if needed, bump version, create a new release |

## Retry discipline

### Retry is allowed when

- the already-built artifact is correct;
- only an external service or verification step failed;
- the retry does not require changing the tag, source commit, version, or artifact bytes.

Examples:

```text
index propagation delay
temporary PyPI outage
temporary GitHub outage
post-publish smoke-test network failure
GitHub release verification timeout
```

Rerun the smallest failed job possible.

### Retry is not allowed when

A code, packaging, metadata, or artifact change is required.

Do not:

```text
move the existing release tag
force-push a release tag
rebuild different bytes under the same version
delete and re-upload the same PyPI filename
replace immutable GitHub Release assets
```

Instead, increment the version.

For the first alpha, the normal fix-forward version is:

```text
0.1.0a1
   ↓
0.1.0a2
```

## PyPI rollback policy

There is no byte-level rollback for a published PyPI version.

A distribution filename is not reusable, including after file/project deletion.

Therefore an incorrect public package follows:

```text
detect issue
    ↓
yank affected release
    ↓
record reason
    ↓
fix on main
    ↓
increment version
    ↓
full release pipeline again
```

A yanked release is normally ignored by dependency resolution but can still be installed when a user explicitly requests that exact version.

This makes yanking appropriate for warning users while preserving reproducibility for exact pins.

## TestPyPI recovery

TestPyPI is treated with the same identity discipline as production.

Do not plan on deleting a bad TestPyPI artifact and reusing the same filename.

If a different artifact is needed:

```text
bump version
→ rebuild
→ retest
```

## GitHub Immutable Release recovery

With Immutable Releases enabled:

- the published release tag cannot be moved;
- release assets cannot be replaced or deleted;
- the tag cannot be deleted while the immutable release exists;
- deleting the immutable release does not make the same tag name reusable.

Therefore an immutable release is a permanent identity record.

If a published release is defective, preserve the record and fix forward with a new version.

Release notes may be edited to add a warning or point users to the corrected version.

## Security incident

If a release is suspected to be malicious or compromised:

1. stop any remaining downstream release jobs;
2. yank the affected PyPI release;
3. document the reason publicly;
4. preserve evidence: workflow run, checksums, attestations, commit SHA;
5. investigate credential/repository compromise;
6. rotate credentials only if any credential was actually exposed;
7. fix on `main`;
8. increment the version;
9. run Release Readiness again;
10. publish a new immutable release.

Never attempt to hide the incident by replacing artifacts under the same release identity.

## Changelog discipline

Before a tag is created, move release notes out of the rolling `[Unreleased]` section into a dated version heading:

```text
## [0.1.0a1] - 2026-10-08
```

After the release, future changes go back under:

```text
## [Unreleased]
```

The release preflight enforces the existence of the dated heading.

## Post-release operator verification

After the workflow is fully green:

```bash
python -m pip install --pre --upgrade pyschedulekit==0.1.0a1

python -c "import pyschedulekit; print(pyschedulekit.__version__)"
```

Expected:

```text
0.1.0a1
```

Verify GitHub build provenance:

```bash
gh attestation verify \
  pyschedulekit-0.1.0a1-py3-none-any.whl \
  --repo tawounfouet/pyschedulekit
```

Verify immutable GitHub Release:

```bash
gh release verify v0.1.0a1
```

## Release records to retain

For each release retain:

```text
version
tag
commit SHA
workflow run URL
wheel filename
sdist filename
SHA-256 manifest
TestPyPI status
PyPI status
GitHub Release URL
build attestation
immutable-release attestation
incident notes, if any
```

The immutable public systems remain the primary evidence; local copies are supplemental.

## Definition of done

REL-08 implementation is complete when:

1. the preflight script is tested;
2. Release Readiness is manual-only and creates no tag;
3. the release tag cannot already exist;
4. external controls require explicit acknowledgement;
5. a full distribution rehearsal executes before go-live;
6. changelog freezing is enforced;
7. go/no-go conditions are explicit;
8. failures map to deterministic recovery actions;
9. published versions are never overwritten;
10. rollback is defined as yank + fix-forward where necessary.

## Roadmap

```text
RELEASE ENGINEERING & DISTRIBUTION
────────────────────────────────────────────────────────
REL-00  Distribution Contract                     ✅
REL-01  Wheel + sdist Build                        ✅
REL-02  Artifact / Metadata Validation             ✅
REL-03  Clean-Install Matrix                       ✅
REL-04  Version / Tag / Release Candidate Gate     ✅
REL-05  TestPyPI Trusted Publishing                🟡 READY
REL-06  PyPI Trusted Publishing                    🟡 READY
REL-07  GitHub Release + Provenance                🟡 READY
REL-08  Release Runbook / Rollback Discipline      ✅

RELEASE ENGINEERING IMPLEMENTATION COMPLETE
GO-LIVE PENDING EXTERNAL CONTROLS
```

## Next operational milestone

There is no REL-09.

The next step is operational activation:

1. configure GitHub environments;
2. register TestPyPI Trusted Publisher;
3. register PyPI Trusted Publisher;
4. enable GitHub Immutable Releases;
5. run Release Readiness;
6. review GO / NO-GO;
7. create and push `v0.1.0a1`.
