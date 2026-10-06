# PyScheduleKit

> Learn scheduling by building a scheduling framework.

PyScheduleKit is a Python scheduling framework designed first as a rigorous learning project: model time, triggers, schedules, occurrences, execution requests, retries, persistence, recovery, and distributed coordination before hiding those concepts behind convenience APIs.

## Project status

**Early implementation — LOT-00: Repository & Packaging Foundation**

The implementation follows a domain-first roadmap:

```text
Time → Trigger → Schedule → Occurrence → SchedulerEngine
     → Execution → Runtime → Persistence → Recovery → Distribution
```

The first executable milestone is intentionally small:

```text
MutableClock
    ↓
IntervalTrigger(10m)
    ↓
Schedule
    ↓
run_pending()
    ↓
exactly one successful local Execution
```

## Architectural principles

- Domain logic stays independent from infrastructure.
- Time is explicit and testable; no hidden wall-clock access in the domain.
- Triggers calculate temporal occurrences; they do not execute work.
- Schedule and Execution have distinct lifecycles.
- Repositories never commit implicitly.
- External side effects never precede durable intent once persistence is enabled.
- Configuration is declarative data, not executable code.
- Every supported guarantee must map to an executable test.

## Planned package shape

```text
src/pyschedulekit/
├── domain/
├── application/
├── ports/
├── infrastructure/
└── testing/
```

The directory structure will grow only when implementation needs it; the project avoids creating empty architectural ceremony before the first working vertical slice.

## Development

Target baseline: **Python 3.11+**.

Once the LOT-00 tooling is merged:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e ".[dev]"
pytest
ruff check .
mypy src
```

## Roadmap

Initial implementation path:

1. Repository & packaging foundation
2. Time model
3. Trigger foundations
4. Date/Interval triggers
5. Schedule aggregate
6. Occurrence planning
7. In-memory persistence
8. Scheduler engine
9. Execution lifecycle
10. Local executor
11. `run_pending()`

Cron, continuous runtime, policies, durable persistence, outbox, crash recovery, and distributed coordination are layered on only after the in-memory scheduling semantics are proven.

## License

MIT
