# PyScheduleKit — POST-00 Remediation Status

> **Current-state companion to the 2026-10-08 audit**
>
> The root audit documents (`CODEBASE_ANALYSIS.md`, `ANALYSE_CRITIQUE.md`,
> `RECOMMANDATIONS.md`) are preserved as an **audit snapshot**. They describe what was
> observed on 2026-10-08 and are not rewritten to pretend those findings never existed.
>
> This document records what changed afterwards and is the authoritative remediation
> status for findings B1–B12.

## 1. Current baseline

- Public release: `0.1.0a3`
- GitHub release: `v0.1.0a3`, published as an immutable prerelease
- Runtime dependencies: 0
- Supported Python: 3.11 / 3.12 / 3.13
- Current hardening target: `0.1.0a4`
- POST-00 theme: post-release stabilization and adversarial hardening

At the completed POST-00 baseline `main@678d1825720d1f3b8a5e46467f2784c599682461`, the combined CI and
Distribution Qualification workflows are green on Python 3.11, 3.12 and 3.13.

## 2. Audit finding disposition

| Finding | Original concern | Current status | Evidence |
|---|---|---|---|
| B1 | Cancellation could lose to timeout/retry | **FIXED** | `c0601e9` — cancellation wins over retry on timeout path + regression tests |
| B2 | Concurrent transition could escape `run_pending()` and kill the continuous runtime | **FIXED** | PR #44 / `0a5455b` — transition-race handling + runtime failure supervision |
| B3 | Ruff formatting failure in release preflight | **FIXED** | `394c246` — release preflight formatted; later quality gates remain green |
| B4 | GitHub Release missing/broken during release-candidate flow | **HISTORICAL / RESOLVED** | `ad4a494` finalized the direct PyPI go-live path; immutable `v0.1.0a3` release exists with wheel, sdist and checksum |
| B5 | Concurrent SQLite bootstrap race | **FIXED** | PR #45 / `f310994` — concurrency-safe schema bootstrap tests |
| B6 | Admission lock could survive a persistence conflict | **FIXED** | PR #46 / `0fe4d8a` — explicit conflict recovery + regression coverage |
| B7 | Implicit target registration occurred before schedule commit | **FIXED** | PR #51 / `1c3e31c` — identity-guarded compensation on failed schedule creation |
| B8 | In-memory referential behavior diverged from SQLite | **FIXED** | PR #48 / `cbf3904` — adapter parity contract + aligned memory semantics |
| B9 | In-memory staged state was inconsistent across repository reads | **FIXED** | PR #48 / `cbf3904` — shared parity tests and staged-state alignment |
| B10 | HTTP failure resources / redirect behavior insufficiently hardened | **FIXED** | PR #49 / `c1c85e3` — deterministic response cleanup + bounded same-host redirects |
| B11 | README version/status lagged behind the published package | **FIXED** | `7ac7fb8` updated the post-release README baseline; POST-00H refreshes release status again |
| B12 | Domain specifications were not versioned | **FIXED** | `0d09e34` — `docs/specs/` tracked and formatted |

No B1–B12 finding remains open after POST-00G + the B7 closure.

## 3. POST-00 execution record

| Step | Scope | Status | Evidence |
|---|---|---|---|
| 00.A | Restore Green Main / isolate raw transcripts | **DONE** | PR #43 / `6b838d7` |
| 00.B | Runtime transition-race hardening | **DONE** | PR #44 / `0a5455b` |
| 00.C | SQLite concurrent bootstrap | **DONE** | PR #45 / `f310994` |
| 00.D | Admission-lock conflict recovery | **DONE** | PR #46 / `0fe4d8a` |
| 00.E | Persistence adapter contract | **DONE** | PR #48 / `cbf3904` |
| 00.F | HTTP resource / redirect hardening | **DONE** | PR #49 / `c1c85e3` |
| 00.G | CI / coverage hardening | **DONE** | PR #50 / `fed749e` |
| B7 closure | Target-registry transaction safety | **DONE** | PR #51 / `1c3e31c` |
| 00.H | Audit documentation consolidation | **DONE** | PR #52 / `678d182` — snapshots, current-state register, transcript archive |

PR #47 was an intermediate persistence-contract proposal and was closed as superseded by
the merged PR #48.

## 4. What POST-00 changed structurally

### 4.1 Runtime survivability

Expected concurrent state changes no longer escape as fatal cycle errors. The runtime also
has an explicit supervision boundary so an isolated cycle failure is observed and does not
permanently terminate long-running scheduling.

### 4.2 Persistence parity

In-memory and SQLite adapters are no longer trusted merely because they implement the same
port. They are exercised through shared contract/parity tests so the same operation must
produce the same observable semantics.

This contract is the basis future persistence adapters, including PostgreSQL, must satisfy.

### 4.3 SQLite bootstrap safety

Schema initialization is now qualified under concurrent initializers rather than only
single-process startup.

### 4.4 Admission safety

A failed persistence mutation after admission-lock acquisition no longer leaves an
artificial lock stall until TTL expiry.

### 4.5 Target registry safety

Implicit local callable registration is treated as compensable process-local state.
If schedule creation does not commit, the exact registration created by that call is
removed, including its cancellation/fencing capability metadata.

The compensation is identity-guarded so it cannot remove a different callable.

### 4.6 HTTP executor hardening

HTTP error responses are closed deterministically and redirect behavior is explicit and
bounded. Redirects remain restricted to safe HTTP(S) behavior without silently widening the
trusted target selected by the caller.

### 4.7 CI as an executable gate

POST-00G made the quality policy executable:

- Ruff is version-pinned for deterministic formatting/linting.
- GitHub Actions are pinned.
- branch coverage is measured.
- `fail_under = 85` is enforced.
- acceptance/public-package qualification is part of the maintained test surface.
- Python 3.11 / 3.12 / 3.13 remain mandatory.
- wheel and sdist clean-install qualification remain mandatory.

## 5. Snapshot versus current-state rule

The documentation now follows this rule:

```text
AUDIT SNAPSHOT
    describes what was observed at a point in time
    keeps original findings and evidence
    is not rewritten after fixes

CURRENT STATE
    describes what is true now
    references remediation commits / PRs / regression tests
    is updated when behavior or release state changes
```

Accordingly:

- `CODEBASE_ANALYSIS.md` remains the factual 2026-10-08 snapshot.
- `ANALYSE_CRITIQUE.md` remains the opinion based on that snapshot.
- `RECOMMANDATIONS.md` remains the remediation plan produced from that snapshot.
- this file is the authoritative disposition of the findings.
- `README.md`, `AGENTS.md`, `ARCHITECTURE.md` and `INDEX.md` describe the current operational state.

## 6. Release-engineering reality

The public go-live path actually used for `0.1.0a3` is:

```text
Tag
 ↓
Qualification
 ↓
PyPI Trusted Publishing
 ↓
Verification from PyPI
 ↓
GitHub Release
 ↓
Provenance / immutable release evidence
```

TestPyPI remains useful as release-engineering history/tooling, but it is not an obligatory
step in the final `0.1.0a3` go-live path.

The published GitHub Release contains:

- `pyschedulekit-0.1.0a3-py3-none-any.whl`
- `pyschedulekit-0.1.0a3.tar.gz`
- `release-candidate-sha256.txt`

## 7. POST-00 Definition of Done status

```text
[x] main green on Python 3.11 / 3.12 / 3.13
[x] raw audit transcripts cannot break Ruff formatting
[x] B2 fixed and regression-covered
[x] B5 fixed and regression-covered
[x] B6 fixed and regression-covered
[x] B7 fixed and regression-covered
[x] B8/B9 covered by persistence adapter parity tests
[x] B10 fixed
[x] redirect policy explicit
[x] coverage threshold >= 85 enforced
[x] acceptance qualification integrated
[x] audit/current-state separation documented
[x] no known open B1-B12 finding
[x] Distribution Qualification green
[ ] final 0.1.0a4 release qualification
[ ] publish 0.1.0a4
```

## 8. Next gate

POST-00H is merged. The remaining sequence is deliberately small:

```text
0.1.0a4 release preparation
        ↓
Release Readiness on main
        ↓
v0.1.0a4 tag pipeline
        ↓
0.1.0a4 public
        ↓
POST-01 / POST-02 / POST-03 / POST-04
        ↓
evidence from real use
        ↓
0.2.x — Execution & Storage Ecosystem
```

No PostgreSQL, Async Executor, new trigger family, CLI, FastAPI adapter or Py*Kit
integration belongs in `0.1.0a4`.

---

**Last refreshed:** 2026-10-09  
**Public reference release:** `0.1.0a3`  
**Hardening target:** `0.1.0a4`
