# POST-04 — Installed-Package Dogfooding

POST-04 verifies PyScheduleKit as a **consumer would use it**, rather than only from inside
the repository test suite.

## Goal

The dogfood boundary is:

```text
build wheel / sdist
      ↓
install artifact into clean Python
      ↓
leave repository source tree
      ↓
run consumer-owned application
      ↓
exercise stable public API + SQLite runtime behavior
```

The consumer is [`dogfood/consumer_app.py`](../../dogfood/consumer_app.py).

It intentionally imports framework objects only from:

```python
from pyschedulekit import ...
```

No `pyschedulekit.domain`, `application`, `infrastructure`, or other internal module is
used by the consumer.

## Scenario

The consumer performs a compact realistic workflow:

1. create a SQLite-backed Scheduler;
2. register a trusted target;
3. persist an interval Schedule;
4. execute the first attempt and force a transient failure;
5. observe `RETRY_WAIT`;
6. advance a consumer-owned deterministic clock;
7. execute the retry successfully;
8. construct a new Scheduler over the same SQLite database;
9. register process-local trusted code again;
10. inspect the persisted Schedule;
11. cross recovery/reconciliation startup barriers;
12. verify readiness + health;
13. pause and resume the persisted Schedule.

Expected terminal output:

```text
dogfood-ok version=<source-version> attempts=2 persisted=True ready=True state=active
```

## Why this is different from ordinary tests

Normal unit/integration/e2e tests run from the repository checkout.

POST-04 adds a distribution-level consumer check:

```text
cwd = /tmp
installed package = wheel or sdist artifact
consumer source = repository-owned external app
framework import = installed site-packages
```

Because the source tree is not the working directory and `src/` is not added to
`PYTHONPATH`, the import resolves from the installed distribution.

## CI qualification

`.github/workflows/distribution.yml` runs the consumer after the existing installed-package
smoke test for all six clean-install combinations:

```text
Python 3.11 × wheel
Python 3.11 × sdist
Python 3.12 × wheel
Python 3.12 × sdist
Python 3.13 × wheel
Python 3.13 × sdist
```

This means a change can pass repository tests yet still fail POST-04 if the built package is
not usable through its public contract.

## Local use

From an environment where PyScheduleKit is installed:

```bash
cd /tmp
python /path/to/pyschedulekit/dogfood/consumer_app.py
```

For the closest reproduction of CI, first build and install one distribution artifact.

## Scope boundary

POST-04 is intentionally local and deterministic:

- no PyPI dependency;
- no network services;
- no external database;
- no hidden wall clock;
- no private framework imports.

POST-05 measures performance. POST-06 introduces controlled faults/chaos.

---

**Status:** POST-04 — Dogfooding.
