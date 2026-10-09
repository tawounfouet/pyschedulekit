# PyScheduleKit Documentation

This directory is the canonical entry point for project documentation.

PyScheduleKit distinguishes two kinds of documents:

```text
CURRENT
    describes the repository as it behaves now
    may evolve with implementation

SNAPSHOT / HISTORY
    records what was observed or decided at a specific point in time
    remains preserved for traceability
```

## Current references

| Document | Purpose |
|---|---|
| [Project README](../README.md) | Product overview, capabilities, development baseline |
| [Architecture](./ARCHITECTURE.md) | Current system structure, flows, invariants and limitations |
| [SDLC](./SDLC.md) | Current development, testing, review and maintenance workflow |
| [AGENTS.md](../AGENTS.md) | Operational guidance for humans and agents working in the repository |
| [CHANGELOG](../CHANGELOG.md) | Version history and unreleased changes |
| [POST-00 remediation status](./audit/2026-10-08/POST_00_REMEDIATION_STATUS.md) | Authoritative disposition of audit findings B1–B12 |

## Documentation areas

```text
docs/
├── README.md                  # this navigation hub
├── ARCHITECTURE.md            # current technical reference
├── SDLC.md                    # current engineering lifecycle
├── api/                       # stable public API reference
├── async/                     # async Python execution adapter
├── audit/
│   └── 2026-10-08/            # dated OpenCode audit archive
├── benchmarks/                # reproducible performance methodology
├── calendars/                 # versioned business-calendar foundations
├── chaos/                     # deterministic fault-injection campaign
├── composites/                # 0.4.x composite-trigger roadmap
├── cookbook/                  # runnable real-world usage scenarios
├── dogfood/                   # installed-distribution consumer qualification
├── executors/                 # explicit executor plugin registry
├── implementation/            # LOT-00 ... LOT-34 implementation records
├── postgres/                  # 0.2.x PostgreSQL adapter roadmap
├── release/                   # release engineering and rollback discipline
└── specs/                     # domain / architecture / acceptance specifications
```

## Audit archive — 2026-10-08

The original audit is intentionally preserved under
[`docs/audit/2026-10-08/`](./audit/2026-10-08/README.md).

| Snapshot | Purpose |
|---|---|
| [CODEBASE_ANALYSIS](./audit/2026-10-08/CODEBASE_ANALYSIS.md) | Verified facts and original B1–B12 findings |
| [ANALYSE_CRITIQUE](./audit/2026-10-08/ANALYSE_CRITIQUE.md) | Critical assessment based on the audited state |
| [RECOMMANDATIONS](./audit/2026-10-08/RECOMMANDATIONS.md) | Original remediation plan |
| [POST-00 status](./audit/2026-10-08/POST_00_REMEDIATION_STATUS.md) | What was subsequently fixed and how |
| [Raw sessions](./audit/2026-10-08/sessions/) | Versioned audit transcripts, excluded from Ruff formatting |

Do not interpret red states inside the three snapshot documents as current repository state.

## Current project sequence

```text
LOT-00 ... LOT-34                     ✅ initial functional roadmap
POST-00 Audit Remediation             ✅ complete
POST-01 Documentation Cleanup         ✅
POST-02 Real-world Examples/Cookbook  ✅
POST-03 API Documentation             ✅
POST-04 Dogfooding                    ✅
POST-05 Benchmarks                    ✅
POST-06 Chaos / Fault Injection       ✅
        ↓
0.2.x Execution & Storage Ecosystem   ✅ complete
  PG-00 PostgreSQL Foundation         ✅
  PG-01 Core Repositories             ✅
  PG-02 Coordination/Outbox/Retention ✅
  PG-03 Adapter Parity Contract        ✅
  PG-04 Scheduler/Multi-worker E2E     ✅
  PG-05 Production Hardening           ✅
        ↓
  Async Python Executor                 ✅
  Executor Plugin Registry              ✅
        ↓
0.3.x Advanced Scheduling               ✅ complete
  CAL-00 Calendar Foundations             ✅
  CAL-01 Schedule Calendar Binding        ✅
  CAL-02 Calendar-aware Planning          ✅
  CAL-03 Business-Day Trigger Semantics   ✅
  CAL-04 Persistence / Migration Parity    ✅
  CAL-05 Calendar Provider Adapters          ✅
        ↓
0.4.x Composite Trigger Foundations  ⏳ in progress
  CMP-00 Composite Trigger Contract  ✅
  CMP-01 ... CMP-05                  ⬜ planned
        ↓
1.0.0 stable public contract
```

## Publication policy

The last currently published PyPI prerelease is `0.1.0a3`.

Development versions after that may advance without a matching public package. The release
workflow now enforces:

```text
0.x            → never publish to PyPI
1.0.0a*        → never publish to PyPI
1.0.0b*        → never publish to PyPI
1.0.0rc*       → never publish to PyPI
stable >=1.0.0 → eligible for PyPI publication
```

This keeps pre-1.0 work focused on framework maturity rather than release ceremony.

## Quick navigation

| I want to… | Read |
|---|---|
| understand the package quickly | [README](../README.md) |
| understand `run_pending()` / runtime / persistence flows | [Architecture](./ARCHITECTURE.md) |
| run or modify the engineering workflow | [SDLC](./SDLC.md) + [AGENTS](../AGENTS.md) |
| understand why POST-00 existed | [Audit critique](./audit/2026-10-08/ANALYSE_CRITIQUE.md) |
| verify whether an audit finding is still open | [POST-00 status](./audit/2026-10-08/POST_00_REMEDIATION_STATUS.md) |
| inspect original design intent | [Specs](./specs/) |
| inspect implementation history | [Implementation LOTs](./implementation/) |
| inspect the stable public API | [API reference](./api/README.md) |
| run trusted async Python workloads | [Async Python Executor](./async/README.md) |
| register custom executor plugins | [Executor Plugin Registry](./executors/README.md) |
| model versioned business calendars | [Calendar Foundations](./calendars/README.md) |
| follow composite-trigger delivery | [Composite Triggers 0.4.x](./composites/README.md) |
| run realistic usage examples | [Cookbook](./cookbook/README.md) |
| inspect installed-package dogfooding | [Dogfooding](./dogfood/README.md) |
| run reproducible performance measurements | [Benchmarks](./benchmarks/README.md) |
| inspect deterministic fault-injection qualification | [Chaos](./chaos/README.md) |
| follow PostgreSQL adapter delivery | [PostgreSQL 0.2.x](./postgres/README.md) |
| understand release safety / fix-forward rules | [Release docs](./release/) |

## Documentation rule

When behavior changes:

1. update executable tests first;
2. update current documentation if the behavior is user- or maintainer-visible;
3. never rewrite a dated snapshot to pretend an old finding never existed;
4. prefer one canonical current document over multiple competing status pages.

---

**Last refreshed:** 2026-10-09 — CMP-00 Composite Trigger Contract complete.
