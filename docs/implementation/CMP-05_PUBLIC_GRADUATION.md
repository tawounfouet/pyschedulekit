# CMP-05 — Public Graduation

## Objective

Graduate the already-qualified pure temporal union into the stable consumer contract only
after domain, recovery, codec, migration and live-adapter guarantees are executable.

## Stable surface

`AnyOfTrigger` is exported with identical object identity from both supported namespaces:

```python
from pyschedulekit import AnyOfTrigger
import pyschedulekit.api as psk

assert AnyOfTrigger is psk.AnyOfTrigger
```

The export is recorded in the sorted `STABLE_PUBLIC_NAMES` manifest, mirrored by the package
root, verified again from every clean-installed wheel/sdist, and documented in the public API
reference. Existing composite-specific error classes remain implementation details,
consistent with the other built-in Trigger families.

## Public end-to-end path

The public Scheduler qualification covers the overlapping union of 10-minute and 15-minute
intervals:

```text
10 → 15 → 20 → 30 → 40
                 ↑
       both children produce 30,
       one execution is materialized
```

A second E2E test persists the same public trigger through SQLite, executes the first
occurrence, opens a fresh Scheduler and observes the next union checkpoint.

## Consumer documentation

The API reference records the supported boundary:

- two or more pure temporal children;
- nested-union flattening;
- maximum flattened fan-out of 64;
- duplicate-free shared Instants;
- durable InMemory/SQLite/PostgreSQL behavior;
- no calendar-aware children or intersection semantics.

The sixth cookbook program executes the overlapping-cadence scenario under the normal test
suite, with no network access, credentials or wall-clock sleeps.

## Performance evidence

The reproducible benchmark harness adds `any_of_next_after`. It repeatedly advances through
two anchored interval streams with overlapping candidates. Both smoke and standard profiles
measure it; CI treats timings as recorded evidence rather than an unstable threshold.

## Acceptance guarantees

- the stable API manifest exports `AnyOfTrigger` from root and `pyschedulekit.api`;
- clean-installed wheels and sdists preserve the same root/API export identity;
- public Scheduler usage is chronologically ordered and duplicate-free;
- the public definition/checkpoint survives SQLite reopen;
- the cookbook scenario is executable in acceptance CI;
- the benchmark emits structured AnyOf evidence;
- documentation states the deliberately unsupported boundaries;
- the base package keeps zero runtime dependencies.

---

**Status:** CMP-05 — Public Graduation implemented and locally qualified; the 0.4.x sequence
is complete.
