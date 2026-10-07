# LOT-18 — Continuous Scheduler Loop

## Goal

Turn the one-shot `run_pending()` primitive into a continuous fixed-cadence runtime.

The loop remains intentionally simple:

```text
run_pending()
    ↓
wait poll_interval
    ↓
run_pending()
    ↓
wait poll_interval
    ↓
...
```

LOT-18 does not calculate the optimal next wake-up time. That belongs to LOT-19.

## Public API

```python
scheduler.run_forever(
    poll_interval=Duration.seconds(1),
    limit=100,
)
```

The method is blocking and keeps calling the same qualified `run_pending()` primitive.

Stopping is explicit:

```python
scheduler.stop()
```

Runtime state is observable through:

```python
scheduler.is_running
scheduler.cycles_completed
scheduler.last_result
```

## Fixed cadence semantics

LOT-18 uses a fixed polling interval.

The default public cadence is one second.

```text
cycle N
  ↓
run_pending()
  ↓
wait poll_interval
  ↓
cycle N+1
```

The wait starts after each completed cycle. Runtime work duration is therefore not hidden inside a fixed-rate clock schedule.

## Interruptible waiting

The production waiter uses `threading.Event.wait()`.

That gives two important properties:

- the runtime does not busy-loop;
- `stop()` interrupts the current wait immediately.

A 30-second polling interval therefore does not imply a 30-second stop latency.

## Memory bounds

`run_forever()` does not retain the history of every cycle.

Only:

```text
cycles_completed
last_result
```

are retained.

This keeps long-running scheduler memory usage bounded.

## Reentrancy

One `ContinuousSchedulerLoop` instance may run only once concurrently.

A second concurrent start raises:

```text
RuntimeAlreadyRunningError
```

The same runtime may be started again after the previous loop has stopped.

## Relationship with run_pending()

LOT-18 does not duplicate scheduling logic.

```text
ContinuousSchedulerLoop
        ↓
RunPendingService.run_pending()
        ↓
existing LOT-11 → LOT-17 pipeline
```

Therefore misfire, catch-up, concurrency, retry, timeout and cancellation semantics remain owned by the existing one-shot pipeline.

## Stop semantics

`stop()` requests termination.

LOT-18 guarantees that it interrupts runtime waiting. It does not yet define advanced shutdown behavior for work already running.

That distinction is deliberate:

```text
LOT-18
→ stop the scheduler loop

LOT-20
→ graceful shutdown semantics for in-flight work
```

## Safety properties

1. `run_pending()` remains the single cycle primitive;
2. no busy-looping;
3. polling cadence must be strictly positive;
4. per-cycle limit remains configurable;
5. waiting is interruptible;
6. only one concurrent loop per runtime instance;
7. runtime memory remains bounded;
8. public state reports whether the loop is running;
9. stop requests are idempotent;
10. adaptive wake-up logic is deferred to LOT-19.

## Qualification

LOT-18 qualifies:

- repeated fixed-cadence invocation;
- propagation of the per-cycle limit;
- invalid poll interval rejection;
- duplicate concurrent start rejection;
- idempotent stop requests;
- execution of newly due work while the loop is running;
- interruption of a long poll wait;
- bounded runtime state.

## Non-goals

LOT-18 does not implement:

- next-due-time wake-up calculation;
- scheduler wake-up notifications after mutations;
- graceful waiting for in-flight work;
- signal handlers;
- async runtime;
- multi-process runtime coordination;
- distributed scheduler leadership.

## Next

`LOT-19 — Wake-up Strategy`
