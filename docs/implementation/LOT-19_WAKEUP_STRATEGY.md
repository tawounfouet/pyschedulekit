# LOT-19 — Wake-up Strategy

## Goal

Replace fixed polling as the primary runtime wait decision with an adaptive wake-up strategy derived from durable scheduler state.

The runtime loop remains:

```text
run_pending()
    ↓
WakeUpPlanner
    ↓
next useful delay
    ↓
interruptible wait
    ↓
run_pending()
```

## Wake-up horizons

LOT-19 considers:

```text
PENDING ExecutionRequest
→ immediate wake-up

QUEUED Execution
→ immediate wake-up

RETRY_WAIT Execution
→ next_attempt_at

ACTIVE Schedule
→ next_run_time

WAITING_ADMISSION
→ no exact temporal horizon
→ max_sleep fallback
```

The earliest known durable horizon wins.

## max_sleep

The public runtime now uses a safety ceiling:

```python
scheduler.run_forever(
    max_sleep=Duration.seconds(30),
)
```

If the next event is 5 seconds away, the runtime waits 5 seconds.

If the next known event is 10 minutes away, the runtime waits at most 30 seconds.

If no exact event is known, it also waits at most 30 seconds.

This preserves periodic reconciliation while avoiding unnecessary short polling.

## Backward compatibility

The LOT-18 argument:

```python
poll_interval = ...
```

remains accepted as an alias for `max_sleep`.

Passing both is rejected.

## Mutation-driven wake-up

Durable state may change while the runtime is sleeping.

LOT-19 therefore adds an explicit wake signal.

Public mutations such as:

```text
add_schedule()
cancel_execution()
```

signal the runtime after their durable commit.

The current wait is interrupted and the wake-up plan is recomputed from committed state.

## Lost-wake protection

The runtime clears the wake signal before computing the next durable horizon.

This gives safe ordering:

```text
clear wake signal
    ↓
read durable state
    ↓
compute delay
    ↓
wait
```

A mutation before the read is visible in durable state.

A mutation after the clear sets the wake event and interrupts the wait.

## WAITING_ADMISSION

A waiting-admission request is deliberately not treated as immediately runnable.

Doing so could create:

```text
run_pending
→ admission still blocked
→ zero delay
→ run_pending
→ admission still blocked
→ ...
```

Instead, admission waiting is re-evaluated on:

- another runtime mutation;
- another exact scheduler event;
- the `max_sleep` reconciliation ceiling.

## Retry interaction

Retry deadlines are first-class wake-up horizons:

```text
Execution RETRY_WAIT
    ↓
next_attempt_at
    ↓
WakeUpPlanner
    ↓
sleep until retry deadline
```

A retry that is earlier than the next Schedule occurrence wakes the runtime first.

## Runtime waiting

`EventLoopWaiter` now waits on a generic wake event.

Both:

```text
Scheduler.stop()
runtime mutation
```

interrupt that wait.

After an interruption, the loop distinguishes stop state from a normal wake and either terminates or runs another cycle.

## Safety properties

1. `run_pending()` remains unchanged;
2. durable state drives wake-up planning;
3. due work returns zero delay;
4. retry deadlines participate in planning;
5. schedule deadlines participate in planning;
6. `max_sleep` bounds reconciliation latency;
7. WAITING_ADMISSION does not cause a busy loop;
8. runtime mutations interrupt sleeping;
9. stop remains immediately interruptible;
10. polling remains available only as a safety ceiling.

## Qualification

LOT-19 qualifies:

- no-known-event fallback;
- next Schedule delay;
- due Schedule immediate wake-up;
- PENDING request immediate wake-up;
- WAITING_ADMISSION anti-busy-loop behavior;
- retry deadline precedence;
- `max_sleep` capping;
- mutation-driven interruption of a long runtime wait;
- backward compatibility of `poll_interval`.

## Non-goals

LOT-19 does not implement:

- database notifications;
- LISTEN/NOTIFY;
- distributed wake-up broadcasts;
- leader election;
- graceful shutdown of in-flight work;
- process signals;
- crash reconciliation.

## Next

`LOT-20 — Graceful Shutdown`
