# Audit OpenCode — 2026-10-08

This directory contains the durable archive and current remediation status for the
post-release audit performed on 2026-10-08.

## Snapshot documents

The original audit deliverables remain at the repository root to preserve their existing
links and review history:

- [CODEBASE_ANALYSIS.md](./CODEBASE_ANALYSIS.md) — verified facts and B1–B12 findings;
- [ANALYSE_CRITIQUE.md](./ANALYSE_CRITIQUE.md) — critical assessment based on the snapshot;
- [RECOMMANDATIONS.md](./RECOMMANDATIONS.md) — original remediation plan;
- [ARCHITECTURE.md](../../ARCHITECTURE.md) — current architecture reference;
- [SDLC.md](../../SDLC.md) — current development lifecycle;
- [AGENTS.md](../../../AGENTS.md) — current operational guidance.

The first three are explicitly marked as **AUDIT SNAPSHOT — 2026-10-08**.

## Current remediation state

See [POST_00_REMEDIATION_STATUS.md](./POST_00_REMEDIATION_STATUS.md).

That file is authoritative for the current disposition of B1–B12 and for the POST-00
completion status.

## Raw sessions

Raw agent transcripts are retained for traceability but are not part of the production
quality surface:

- [sessions/codebase-audit.md](./sessions/codebase-audit.md)
- [sessions/end-to-end.md](./sessions/end-to-end.md)

Ruff excludes `docs/audit/**/sessions/**` explicitly. The archive therefore remains
versioned without allowing raw transcript formatting to block code quality gates.
