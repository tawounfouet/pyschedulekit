# REL-05 — TestPyPI Trusted Publishing

## Goal

Publish the exact qualified PyScheduleKit release candidate to TestPyPI without storing a long-lived package index credential in GitHub.

REL-05 uses GitHub Actions OIDC Trusted Publishing.

The target flow is:

```text
tag vX.Y.Z
    ↓
REL-04 qualification
    ↓
qualified artifact + checksums
    ↓
TestPyPI Trusted Publisher
    ↓
OIDC short-lived credential
    ↓
upload exact wheel + sdist
    ↓
install from TestPyPI
    ↓
smoke test
```

## Security boundary

The publishing job is the only job granted:

```yaml
permissions:
  id-token: write
```

It also runs in the dedicated GitHub environment:

```text
testpypi
```

No PyPI/TestPyPI username, API token, password, or repository secret is used.

## Exact Trusted Publisher identity

The TestPyPI publisher configuration must match the workflow identity exactly:

```text
Project name:       pyschedulekit
GitHub owner:       tawounfouet
Repository:         pyschedulekit
Workflow filename:  release-candidate.yml
Environment:        testpypi
```

If the project does not yet exist on TestPyPI, configure a pending GitHub Trusted Publisher for this identity.

A pending publisher becomes a normal publisher on first successful use.

Important: a pending publisher does not reserve the project name before first publication.

## GitHub environment

Create or review the repository environment:

```text
testpypi
```

Recommended protection:

1. restrict deployments to release tags;
2. require manual approval when supported by the repository plan;
3. do not store package-index secrets in the environment;
4. keep the environment name exactly equal to the Trusted Publisher configuration.

## Artifact reuse

REL-05 does not rebuild the package.

The publish job downloads:

```text
release-candidate-dists-<tag>
```

created by the REL-04 qualification job.

Before publishing, it verifies:

```bash
sha256sum --check release-candidate-sha256.txt
```

The uploaded files are therefore the exact bytes previously qualified.

## Publishing action

The workflow uses the official PyPA publication action, pinned to an immutable commit:

```text
pypa/gh-action-pypi-publish
@dc37677b2e1c63e2034f94d8a5b11f265b73ba33
```

The target repository is:

```text
https://test.pypi.org/legacy/
```

PEP 740 attestations remain enabled.

## Trigger restriction

Publication is only reachable for a real pushed release tag:

```yaml
if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')
```

Manual workflow dispatch can qualify a candidate but cannot publish it to TestPyPI.

Pull requests cannot publish.

## Post-publish verification

After a successful upload, a separate job installs:

```text
pyschedulekit==<qualified-version>
```

from:

```text
https://test.pypi.org/simple/
```

with:

```text
--no-deps
```

PyScheduleKit currently has no runtime dependencies, so this verifies the package itself without falling back to PyPI.

The install is retried a bounded number of times to tolerate short TestPyPI indexing delays.

The installed package is then smoke-tested from `/tmp` so the repository checkout cannot shadow it.

## Workflow fitness tests

CI statically enforces that the publishing workflow:

- is tag-only;
- uses environment `testpypi`;
- grants `id-token: write`;
- reuses the retained candidate artifact;
- rechecks SHA-256 checksums;
- does not rebuild in the publish job;
- uses a SHA-pinned PyPA action;
- targets TestPyPI;
- contains no static username/password/token configuration;
- verifies the published package from TestPyPI.

## Activation status

The repository implementation is ready.

Operational completion requires:

```text
[ ] GitHub environment testpypi reviewed/configured
[ ] TestPyPI account available
[ ] pending/existing Trusted Publisher registered
[ ] first real release tag pushed
[ ] TestPyPI upload succeeds via OIDC
[ ] package re-installs from TestPyPI
[ ] post-publish smoke test passes
```

Until these external checks are complete, REL-05 is considered READY rather than fully complete.

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
REL-06  PyPI Trusted Publishing                    ⬜
REL-07  GitHub Release + Provenance                ⬜
REL-08  Release Runbook / Rollback Discipline      ⬜
```

## Next operational step

Register the TestPyPI Trusted Publisher identity, then keep the real `v0.1.0a1` tag on hold until REL-06 is also present in the tagged commit.
