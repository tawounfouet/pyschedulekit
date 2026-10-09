# POST-06 — Deterministic Chaos / Fault Injection

POST-06 turns fault handling into a repeatable qualification campaign.

The harness is [`chaos/run.py`](../../chaos/run.py).

## Principle

Chaos here does **not** mean randomness.

A scheduling framework needs failures that can be replayed exactly:

```text
known initial state
      ↓
inject one explicit fault
      ↓
observe durable/runtime behavior
      ↓
verify safety invariant
      ↓
verify recovery path
```

No external network, random timing, or arbitrary sleeps are required.

## Campaign

### 1. Executor retry recovery

Injected fault:

```text
target attempt 1 → RuntimeError
```

Invariant:

- execution enters retry handling;
- work does not rerun before its backoff deadline;
- the next eligible attempt succeeds;
- no extra attempt is created.

### 2. Outbox broker recovery

Injected fault:

```text
first publisher call → RuntimeError("broker outage")
```

Invariant:

- failed message remains pending;
- other publishable work is not globally lost;
- later dispatch retries the pending message;
- durable pending backlog returns to zero.

This proves at-least-once recovery, not strict broker ordering.

### 3. Runtime cycle supervision

Injected fault:

```text
first run_pending cycle → RuntimeError
```

Invariant:

- `runtime.cycle.error` is observed;
- the continuous loop performs a later successful cycle;
- the isolated fault does not permanently terminate runtime supervision.

### 4. Admission conflict compensation

Injected fault:

```text
persistence conflict after admission-lock acquisition
```

Invariant:

- the owned lock is released immediately;
- a second worker can reacquire without waiting for TTL expiry.

### 5. Stale-owner fencing

Injected fault:

```text
worker A starts Attempt
lease expires
worker B recovers durable state
worker A tries stale SUCCESS commit
```

Invariant:

- recovery advances the fencing generation;
- stale completion is rejected;
- durable execution remains in the recovered terminal state.

## Run locally

```bash
python -m chaos.run
python -m chaos.run --output chaos-results.json
```

Successful campaign summary:

```text
scenario_count = 5
passed         = 5
failed         = 0
deterministic  = true
```

## CI strategy

The scenarios are also exercised by pytest as part of normal CI.

A dedicated `Chaos Qualification` workflow runs after chaos-relevant merges to `main` and
can also be launched manually. It stores `chaos-results.json` for 30 days.

The workflow is evidence-oriented: there is no probabilistic retry loop that can hide an
intermittent failure.

## Relationship to existing tests

POST-00 already added focused regression tests for several individual bugs.

POST-06 does not replace those tests. It layers a campaign over the current architecture so
maintainers can answer a different question:

> after representative faults are injected across multiple subsystems, do the safety and
> recovery invariants still hold together?

## POST roadmap exit

After POST-06, the post-release stabilization/adoption sequence is complete:

```text
POST-01 docs       ✅
POST-02 cookbook   ✅
POST-03 API docs   ✅
POST-04 dogfood    ✅
POST-05 benchmark  ✅
POST-06 chaos      ← current
```

The next roadmap phase is **0.2.x — Execution & Storage Ecosystem**, starting with
PostgreSQL persistence before Async Executor and executor plugin registry work.

---

**Status:** POST-06 — Chaos / Fault Injection.
