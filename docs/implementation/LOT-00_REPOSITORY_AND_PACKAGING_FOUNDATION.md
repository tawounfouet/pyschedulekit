# LOT-00 — Repository & Packaging Foundation

## Goal

Establish the smallest repository foundation required to implement PyScheduleKit without creating empty architectural ceremony.

## Included

- `src/` package layout.
- Python 3.11+ project metadata.
- Empty-runtime-dependency core package.
- Domain / application / ports / infrastructure / testing boundaries.
- Strict type checking baseline.
- Ruff linting and formatting.
- Pytest and coverage tooling.
- Local pre-commit quality gates.
- GitHub Actions CI.
- Architecture fitness tests.

## Architecture fitness rules established

The `pyschedulekit.domain` package must not import:

- `pyschedulekit.application`
- `pyschedulekit.infrastructure`
- `pyschedulekit.ports`
- `pyschedulekit.runtime`
- `pyschedulekit.api`

The domain also must not directly call ambient process/time APIs that future ports are intended to isolate:

- `datetime.now()`
- `datetime.utcnow()`
- `date.today()`
- `time.sleep()`
- `os.getenv()`

These rules are executable tests rather than documentation-only conventions.

## Intentionally deferred

LOT-00 does **not** create speculative implementation modules for:

- Clock
- Instant
- Trigger
- Schedule
- SchedulerEngine
- Execution
- Runtime
- Persistence adapters

Those begin in LOT-01 and later vertical slices.

## Exit criteria

- Package installs in editable mode.
- `import pyschedulekit` succeeds.
- Package exposes version `0.1.0a0`.
- Ruff succeeds.
- Ruff formatting check succeeds.
- Mypy succeeds.
- Pytest succeeds.
- CI executes on supported baseline Python versions.
- Domain architecture fitness checks are green.

## Next lot

`LOT-01 — Time Model`

First implementation objects:

- `Instant`
- `Duration`
- `Timezone`
- `TimeWindow`
- `GracePeriod`
- `Clock`
- `SystemClock`
- `FixedClock`
- `MutableClock`
