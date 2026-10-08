# REL-06 — PyPI Trusted Publishing

## Goal

Promote a release to the production Python Package Index only after the exact same release candidate has passed the complete TestPyPI publication and verification path.

The production path is deliberately downstream from TestPyPI:

```text
qualified candidate
      ↓
TestPyPI publish
      ↓
TestPyPI reinstall
      ↓
TestPyPI smoke test
      ↓
PyPI publish
      ↓
PyPI reinstall
      ↓
PyPI smoke test
```

A production release cannot bypass the TestPyPI gate.

## Trusted Publishing

REL-06 uses PyPI Trusted Publishing through GitHub Actions OIDC.

The PyPI publication job runs with:

```yaml
environment:
  name: pypi

permissions:
  contents: read
  id-token: write
```

No production PyPI password, API token, username, or repository secret is configured.

## Required PyPI publisher identity

The PyPI Trusted Publisher must match exactly:

```text
Project name:       pyschedulekit
GitHub owner:       tawounfouet
Repository:         pyschedulekit
Workflow filename:  release-candidate.yml
Environment:        pypi
```

If the project does not yet exist on PyPI, a pending GitHub Trusted Publisher can be configured for this identity before first upload.

A pending publisher does not reserve the project name before that first successful publication.

## Production environment

Create or review the GitHub Actions environment:

```text
pypi
```

Recommended protections:

1. restrict deployments to release tags;
2. require manual approval where supported;
3. keep the environment free of static PyPI credentials;
4. keep the environment name exactly synchronized with the PyPI Trusted Publisher configuration.

The production environment is intentionally distinct from:

```text
testpypi
```

so TestPyPI and PyPI have separate deployment boundaries and OIDC subjects.

## TestPyPI is a hard prerequisite

The production job declares:

```text
needs:
  qualify-release-candidate
  verify-testpypi
```

Therefore:

```text
TestPyPI upload failure          → PyPI skipped
TestPyPI indexing failure        → PyPI skipped
TestPyPI install failure         → PyPI skipped
TestPyPI smoke-test failure      → PyPI skipped
```

Only a verified TestPyPI release may advance to production.

## Artifact integrity

REL-06 does not rebuild the release.

The PyPI job downloads the same artifact created by REL-04:

```text
release-candidate-dists-<tag>
```

and validates:

```bash
sha256sum --check release-candidate-sha256.txt
```

before publication.

The production upload therefore uses the exact wheel and source distribution already qualified and exercised through TestPyPI.

## Publishing action

The production workflow uses the official PyPA action pinned to the same immutable commit used for TestPyPI:

```text
pypa/gh-action-pypi-publish
@dc37677b2e1c63e2034f94d8a5b11f265b73ba33
```

No `repository-url` override is supplied in the production job, so the action targets the canonical PyPI repository.

PEP 740 attestations are explicitly enabled.

## Trigger restriction

Production publication can only run for a real pushed release tag:

```yaml
if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')
```

Manual workflow dispatch remains qualification-only and cannot publish.

Pull requests cannot publish.

## Post-publish verification

After PyPI accepts the artifacts, a separate job installs:

```text
pyschedulekit==<qualified-version>
```

from:

```text
https://pypi.org/simple/
```

with:

```text
--no-deps
```

The installation is retried a bounded number of times to tolerate short index propagation delays.

The installed distribution is then smoke-tested from `/tmp`, preventing the repository checkout from shadowing the package installed from PyPI.

## End-to-end release promotion

The release workflow now expresses:

```text
TAG
 │
 ▼
REL-04 QUALIFY
 │
 ├── version identity
 ├── metadata
 ├── distributions
 └── checksums
 │
 ▼
REL-05 TESTPYPI
 │
 ├── OIDC publish
 ├── attestation
 ├── reinstall
 └── smoke test
 │
 ▼
REL-06 PYPI
 │
 ├── OIDC publish
 ├── attestation
 ├── reinstall
 └── smoke test
 │
 ▼
PRODUCTION PACKAGE VERIFIED
```

## Workflow fitness tests

CI statically enforces that the production job:

- depends on successful TestPyPI verification;
- is available only for real release-tag pushes;
- uses environment `pypi`;
- grants `id-token: write`;
- reuses the retained release-candidate artifact;
- rechecks SHA-256 checksums;
- contains no rebuild;
- uses the SHA-pinned official PyPA publishing action;
- does not define TestPyPI's repository URL in the production section;
- contains no static PyPI credentials;
- leaves attestations enabled;
- verifies the published package from the PyPI simple index.

## Activation status

The repository implementation is ready.

Operational completion requires:

```text
[ ] GitHub environment testpypi configured
[ ] TestPyPI Trusted Publisher registered
[ ] GitHub environment pypi configured
[ ] PyPI Trusted Publisher registered
[ ] first real release tag pushed
[ ] TestPyPI publication and verification succeed
[ ] PyPI publication succeeds through OIDC
[ ] package re-installs from PyPI
[ ] production smoke test passes
```

Until the external PyPI identity has successfully published through OIDC, REL-06 remains READY rather than complete.

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
REL-07  GitHub Release + Provenance               ⏭ NEXT
REL-08  Release Runbook / Rollback Discipline      ⬜
```

## Next

`REL-07 — GitHub Release + Provenance`
