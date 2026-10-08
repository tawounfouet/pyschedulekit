"""Comprehensive functional exercise of PyScheduleKit's public surface.

Independent end-to-end demonstration covering every feature area, beyond the
unit/integration/e2e suites. Prints a PASS/FAIL ledger.

Run from the repo root:
    /opt/miniconda3/bin/python temp/exercise_pyschedulekit.py
"""

from __future__ import annotations

import tempfile
import threading
import time
import traceback
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pyschedulekit as psk
from pyschedulekit import (
    ConcurrencyOverflowPolicy,
    ConcurrencyPolicy,
    CronTrigger,
    DateTrigger,
    Duration,
    ExecutionState,
    FixedBackoff,
    HttpMethod,
    HttpRequestSpec,
    InMemoryObservationSink,
    Instant,
    IntervalTrigger,
    MisfirePolicy,
    OutboxState,
    PyScheduleKitDeprecationWarning,
    RetentionPolicy,
    RetryPolicy,
    Scheduler,
    ScheduleState,
    ShutdownMode,
    SqliteUnitOfWorkFactory,
    TargetRef,
    Timezone,
)
from pyschedulekit.domain.execution import ExecutionId
from pyschedulekit.domain.execution_request import RequestId
from pyschedulekit.domain.occurrence import OccurrenceKey
from pyschedulekit.domain.schedule import ScheduleId, ScheduleRevision
from pyschedulekit.ports.executor import ExecutorOutcome, PreparedTarget
from pyschedulekit.testing import FixedClock, MutableClock

RESULTS: list[tuple[str, str, str]] = []


def run(name: str, fn) -> None:
    try:
        fn()
    except Exception as exc:
        RESULTS.append((name, "FAIL", f"{type(exc).__name__}: {exc}"))
        print(f"FAIL  {name}: {type(exc).__name__}: {exc}")
        traceback.print_exc(limit=2)
    else:
        RESULTS.append((name, "PASS", ""))
        print(f"PASS  {name}")


def at(hour: int = 10, minute: int = 0, second: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, second, tzinfo=UTC))


def every_10() -> IntervalTrigger:
    return IntervalTrigger(every=Duration.minutes(10), anchor=at(hour=10, minute=10))


def execution_id_for(schedule_id: str, *, hour: int = 10, minute: int = 10) -> ExecutionId:
    request_id = RequestId.for_occurrence(
        OccurrenceKey(
            schedule_id=ScheduleId(schedule_id),
            schedule_revision=ScheduleRevision(1),
            scheduled_at=at(hour=hour, minute=minute),
        )
    )
    return ExecutionId.for_request(request_id)


# 1. time model ------------------------------------------------------------
def time_model() -> None:
    start = at()
    later = start.add(Duration.minutes(5))
    assert later > start
    assert later.elapsed_since(start) == Duration.minutes(5)
    assert start.add(Duration.hours(1)) == at(hour=11)
    assert Timezone("UTC").name == "UTC"


# 2. date trigger ----------------------------------------------------------
def date_trigger() -> None:
    clock = MutableClock(at())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []
    scheduler.add_schedule(
        id="once",
        target=lambda: calls.append("x"),
        trigger=DateTrigger(at=at(hour=10, minute=5)),
    )
    assert scheduler.run_pending().executions == ()
    clock.advance(Duration.minutes(5))
    assert scheduler.run_pending().succeeded == 1 and calls == ["x"]
    clock.advance(Duration.minutes(10))
    assert scheduler.run_pending().executions == ()


# 3. interval trigger ------------------------------------------------------
def interval_trigger() -> None:
    clock = MutableClock(at())
    scheduler = Scheduler(clock=clock)
    calls: list[int] = []
    scheduler.add_schedule(id="interval", target=lambda: calls.append(1), trigger=every_10())
    for _ in range(3):
        clock.advance(Duration.minutes(10))
        scheduler.run_pending()
    assert len(calls) == 3, calls


# 4. cron trigger ----------------------------------------------------------
def cron_trigger() -> None:
    clock = MutableClock(at(hour=10, minute=0))
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []
    scheduler.add_schedule(
        id="cron",
        target=lambda: calls.append("c"),
        trigger=CronTrigger(expression="* * * * *", timezone=Timezone("UTC")),
    )
    assert scheduler.run_pending().executions == ()
    clock.advance(Duration.minutes(1))
    assert scheduler.run_pending().succeeded == 1 and calls == ["c"]


# 5. schedule aggregate ----------------------------------------------------
def schedule_aggregate() -> None:
    clock = MutableClock(at())
    scheduler = Scheduler(clock=clock)
    sid = scheduler.add_schedule(
        id="full",
        target=lambda: None,
        trigger=every_10(),
        timezone=Timezone("UTC"),
        misfire=MisfirePolicy.run_now(),
        concurrency=ConcurrencyPolicy.limit(max_instances=1),
        retry=RetryPolicy(max_attempts=3, backoff=FixedBackoff(Duration.minutes(1))),
        timeout=Duration.minutes(2),
    )
    snap = scheduler.inspect_schedule(sid)
    assert snap.state is ScheduleState.ACTIVE
    assert snap.next_run_time == at(hour=10, minute=10)


# 6. run_pending local -----------------------------------------------------
def run_pending_local() -> None:
    clock = MutableClock(at())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []
    sid = scheduler.add_schedule(id="local", target=lambda: calls.append("ran"), trigger=every_10())
    clock.advance(Duration.minutes(10))
    result = scheduler.run_pending()
    assert calls == ["ran"]
    assert result.succeeded == 1 and result.failed == 0 and result.errors == ()
    assert result.executions[0].execution.state is ExecutionState.SUCCESS
    assert scheduler.inspect_schedule(sid).next_run_time == at(hour=10, minute=20)


# 7. retry fixed backoff ---------------------------------------------------
def retry_fixed() -> None:
    clock = MutableClock(at())
    scheduler = Scheduler(clock=clock)
    calls = 0

    def target() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("transient")

    scheduler.add_schedule(
        id="retry",
        target=target,
        trigger=every_10(),
        retry=RetryPolicy(max_attempts=3, backoff=FixedBackoff(Duration.minutes(5))),
    )
    clock.advance(Duration.minutes(10))
    first = scheduler.run_pending()
    assert first.executions[0].execution.state is ExecutionState.RETRY_WAIT
    assert first.retry_scheduled == 1 and calls == 1
    clock.advance(Duration.minutes(5))
    second = scheduler.run_pending()
    assert second.succeeded == 1 and calls == 2
    assert second.executions[0].execution.attempt_count == 2


# 8. exponential backoff + exhaustion --------------------------------------
def retry_variants() -> None:
    clock = MutableClock(at())
    scheduler = Scheduler(clock=clock)
    calls = 0

    def failing() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("always")

    scheduler.add_schedule(
        id="expo",
        target=failing,
        trigger=every_10(),
        retry=RetryPolicy(
            max_attempts=3,
            backoff=psk.ExponentialBackoff(Duration.minutes(1)),
        ),
    )
    clock.advance(Duration.minutes(10))
    assert scheduler.run_pending().retry_scheduled == 1
    clock.advance(Duration.minutes(2))
    assert scheduler.run_pending().retry_scheduled == 1
    clock.advance(Duration.minutes(4))
    final = scheduler.run_pending()
    assert final.executions[0].execution.state is ExecutionState.FAILED
    assert final.failed == 1 and calls == 3


# 9. execution timeout -----------------------------------------------------
def execution_timeout() -> None:
    clock = MutableClock(at())
    scheduler = Scheduler(clock=clock)
    calls = 0

    def target() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            clock.advance(Duration.seconds(3))

    scheduler.add_schedule(
        id="timeout",
        target=target,
        trigger=every_10(),
        timeout=Duration.seconds(1),
        retry=RetryPolicy(max_attempts=2),
    )
    clock.advance(Duration.minutes(10))
    first = scheduler.run_pending()
    assert first.executions[0].execution.state is ExecutionState.RETRY_WAIT
    second = scheduler.run_pending()
    assert second.executions[0].execution.state is ExecutionState.SUCCESS
    assert second.executions[0].execution.attempt_count == 2


# 10. cancellation through the public API (cooperative) --------------------
def cancellation_public() -> None:
    clock = MutableClock(at())
    scheduler = Scheduler(clock=clock)
    started = threading.Event()

    def target(cancellation_token) -> None:
        started.set()
        while not cancellation_token.is_cancelled:
            time.sleep(0.001)
        cancellation_token.raise_if_cancelled()

    scheduler.add_schedule(
        id="cancel2",
        target=target,
        trigger=every_10(),
        retry=RetryPolicy(max_attempts=3),
    )
    clock.advance(Duration.minutes(10))
    box: list = []
    worker = threading.Thread(target=lambda: box.append(scheduler.run_pending()))
    worker.start()
    assert started.wait(2)
    snap = scheduler.cancel_execution(execution_id_for("cancel2"))
    assert snap.cancellation_requested is True
    worker.join(2)
    result = box[0]
    assert result.executions[0].execution.state is ExecutionState.CANCELLED
    assert result.retry_scheduled == 0


# 11. cancellation vs retry — documented guarantee (LOT-17) ----------------
def cancellation_vs_retry() -> None:
    clock = MutableClock(at())
    scheduler = Scheduler(clock=clock)
    started = threading.Event()
    calls = 0

    def target(cancellation_token) -> None:
        nonlocal calls
        calls += 1
        started.set()
        time.sleep(1.5)  # ignores the token on purpose

    scheduler.add_schedule(
        id="b1",
        target=target,
        trigger=every_10(),
        timeout=Duration.seconds(1),
        retry=RetryPolicy(max_attempts=3, backoff=FixedBackoff(Duration.minutes(1))),
    )
    clock.advance(Duration.minutes(10))
    box: list = []
    worker = threading.Thread(target=lambda: box.append(scheduler.run_pending()))
    worker.start()
    assert started.wait(2)
    scheduler.cancel_execution(execution_id_for("b1"))
    worker.join(3)
    state_after = box[0].executions[0].execution.state
    calls_after_cancel = calls
    clock.advance(Duration.minutes(1))
    scheduler.run_pending()
    print(
        f"      [diagnostic B1] state after cancel={state_after.value}, "
        f"calls_after_cancel={calls_after_cancel}, calls_after_retry_cycle={calls}"
    )
    assert calls == calls_after_cancel, (
        "LOT-17 'cancellation always wins over retry' violated: the cancelled "
        "execution was retried (bug B1)"
    )


# 12. concurrency limit (queue) --------------------------------------------
def concurrency_limit() -> None:
    clock = MutableClock(at())
    # Long lease TTL: a 10-minute clock jump must not expire the running claim
    # (otherwise durable recovery legitimately reclaims it, which is correct
    # multi-worker behaviour but defeats this isolated concurrency check).
    scheduler = Scheduler(clock=clock, claim_ttl=Duration.days(1))
    started = threading.Event()
    release = threading.Event()

    def target() -> None:
        started.set()
        release.wait(3)

    scheduler.add_schedule(
        id="limited",
        target=target,
        trigger=every_10(),
        concurrency=ConcurrencyPolicy.limit(
            max_instances=1,
            overflow=ConcurrencyOverflowPolicy.QUEUE,
        ),
    )
    clock.advance(Duration.minutes(10))
    worker = threading.Thread(target=scheduler.run_pending)
    worker.start()
    assert started.wait(2)
    clock.advance(Duration.minutes(10))
    second = scheduler.run_pending()
    assert second.executions == ()
    assert second.queued_request_ids != () or second.admission_lock_denied_request_ids != ()
    release.set()
    worker.join(2)


# 13. misfire policy -------------------------------------------------------
def misfire_policy() -> None:
    clock = MutableClock(at(hour=9, minute=59))
    scheduler = Scheduler(clock=clock)
    calls: list[int] = []
    scheduler.add_schedule(
        id="misfire",
        target=lambda: calls.append(1),
        trigger=IntervalTrigger(every=Duration.hours(1), anchor=at(hour=10)),
        misfire=MisfirePolicy.run_now(),
    )
    clock.advance(Duration.hours(3))
    assert scheduler.run_pending().succeeded == 1 and calls == [1]


# 14. sqlite persistence ---------------------------------------------------
def sqlite_persistence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "s.db"
        clock = MutableClock(at())
        scheduler = Scheduler(clock=clock, uow_factory=SqliteUnitOfWorkFactory(db))
        calls: list[str] = []
        scheduler.add_schedule(id="persist", target=lambda: calls.append("r"), trigger=every_10())
        clock.advance(Duration.minutes(10))
        assert scheduler.run_pending().succeeded == 1
        with SqliteUnitOfWorkFactory(db)() as uow:
            schedule = uow.schedules.get(ScheduleId("persist"))
            assert schedule is not None
            assert schedule.next_run_time == at(hour=10, minute=20)


# 15. crash recovery across restart ---------------------------------------
def crash_recovery() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "r.db"
        factory = SqliteUnitOfWorkFactory(db)
        from pyschedulekit.application.execution_service import ExecutionService
        from pyschedulekit.domain.execution_request import ExecutionRequest
        from pyschedulekit.domain.occurrence import Occurrence
        from pyschedulekit.domain.schedule import (
            Schedule,
            ScheduleDefinition,
            ScheduleId,
            ScheduleRevision,
            TargetRef,
        )
        from pyschedulekit.domain.triggers import IntervalTrigger

        schedule = Schedule.create(
            schedule_id=ScheduleId("orphan"),
            definition=ScheduleDefinition(
                target=TargetRef.python("jobs:orphan"),
                trigger=IntervalTrigger(every=Duration.hours(1), anchor=at(hour=11)),
                retry=RetryPolicy(max_attempts=2, backoff=FixedBackoff(Duration.minutes(5))),
            ),
            reference=at(hour=9),
        )
        request = ExecutionRequest.from_occurrence(
            occurrence=Occurrence(
                schedule_id=schedule.id,
                schedule_revision=ScheduleRevision(1),
                scheduled_at=at(),
            ),
            target=schedule.definition.target,
            created_at=at(),
            retry_policy=schedule.definition.retry,
        )
        with factory() as uow:
            uow.schedules.add(schedule)
            uow.requests.add(request)
            uow.commit()
        service = ExecutionService(uow_factory=factory)
        execution = service.dispatch(request_id=request.id, created_at=at())
        service.start_attempt(execution_id=execution.id, started_at=at())

        clock = MutableClock(at(minute=1))
        restarted = Scheduler(clock=clock, uow_factory=SqliteUnitOfWorkFactory(db))
        calls: list[str] = []
        restarted.register_target("jobs:orphan", lambda: calls.append("attempt-2"))
        first = restarted.run_pending()
        assert first.executions == ()
        assert restarted.last_recovery_result is not None
        assert restarted.last_recovery_result.retried_execution_ids != ()
        clock.advance(Duration.minutes(5))
        assert restarted.run_pending().succeeded == 1 and calls == ["attempt-2"]


# 16. reconciliation -------------------------------------------------------
def reconciliation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "c.db"
        factory = SqliteUnitOfWorkFactory(db)
        from pyschedulekit.domain.execution_request import ExecutionRequest
        from pyschedulekit.domain.occurrence import Occurrence
        from pyschedulekit.domain.schedule import (
            Schedule,
            ScheduleDefinition,
            ScheduleId,
            ScheduleRevision,
            TargetRef,
        )
        from pyschedulekit.domain.triggers import IntervalTrigger

        schedule = Schedule.create(
            schedule_id=ScheduleId("rec"),
            definition=ScheduleDefinition(
                target=TargetRef.python("jobs:rec"),
                trigger=IntervalTrigger(every=Duration.hours(1), anchor=at(hour=11)),
            ),
            reference=at(hour=9),
        )
        request = ExecutionRequest.from_occurrence(
            occurrence=Occurrence(
                schedule_id=schedule.id,
                schedule_revision=ScheduleRevision(1),
                scheduled_at=at(),
            ),
            target=schedule.definition.target,
            created_at=at(),
        )
        request.mark_dispatched()
        with factory() as uow:
            uow.schedules.add(schedule)
            uow.requests.add(request)
            uow.commit()
        calls: list[str] = []
        scheduler = Scheduler(
            clock=MutableClock(at(minute=1)),
            uow_factory=SqliteUnitOfWorkFactory(db),
        )
        scheduler.register_target("jobs:rec", lambda: calls.append("ran"))
        result = scheduler.run_pending()
        assert scheduler.last_reconciliation_result is not None
        assert scheduler.last_reconciliation_result.reconstructed_execution_ids != ()
        assert result.succeeded == 1 and calls == ["ran"]


# 17. transactional outbox -------------------------------------------------
def outbox() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "o.db"
        clock = MutableClock(at())
        scheduler = Scheduler(clock=clock, uow_factory=SqliteUnitOfWorkFactory(db))
        scheduler.add_schedule(id="ob", target=lambda: None, trigger=every_10())
        clock.advance(Duration.minutes(10))
        scheduler.run_pending()
        with SqliteUnitOfWorkFactory(db)() as uow:
            pending = uow.outbox.list_pending(limit=10)
        assert [m.event_type for m in pending] == [
            "execution.attempt.started",
            "execution.attempt.completed",
        ]
        assert all(m.state is OutboxState.PENDING for m in pending)

        class Publisher:
            def __init__(self) -> None:
                self.messages: list = []

            def publish(self, message) -> None:
                self.messages.append(message)

        publisher = Publisher()
        dispatch = scheduler.dispatch_outbox(publisher)
        assert dispatch.published == 2 and len(publisher.messages) == 2
        with SqliteUnitOfWorkFactory(db)() as uow:
            assert uow.outbox.list_pending(limit=10) == []


# 18. multi-worker claims --------------------------------------------------
def claims() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "cl.db"
        clock = MutableClock(at())
        first = Scheduler(
            clock=clock,
            uow_factory=SqliteUnitOfWorkFactory(db),
            worker_id="a",
            claim_ttl=Duration.seconds(30),
        )
        second = Scheduler(
            clock=clock,
            uow_factory=SqliteUnitOfWorkFactory(db),
            worker_id="b",
            claim_ttl=Duration.seconds(30),
        )
        calls: list[str] = []
        first.add_schedule(id="shared", target=lambda: calls.append("a"), trigger=every_10())
        second.register_target("local:shared", lambda: calls.append("b"))
        clock.advance(Duration.minutes(10))
        assert first.run_pending().succeeded == 1
        assert second.run_pending().succeeded == 0
        assert calls == ["a"]


# 19. multi-worker admission-lock contention -------------------------------
def admission_lock() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "al.db"
        factory = SqliteUnitOfWorkFactory(db)
        from pyschedulekit.application.admission_lock import ScheduleAdmissionLockCoordinator
        from pyschedulekit.domain.claim import WorkerId
        from pyschedulekit.domain.execution_request import ExecutionRequest
        from pyschedulekit.domain.occurrence import Occurrence
        from pyschedulekit.domain.schedule import ScheduleId, ScheduleRevision

        owner = Scheduler(clock=MutableClock(at()), uow_factory=factory, worker_id="a")
        owner.add_schedule(
            id="shared",
            target=lambda: None,
            trigger=IntervalTrigger(every=Duration.hours(1), anchor=at(hour=11)),
            concurrency=ConcurrencyPolicy.limit(
                max_instances=1,
                overflow=ConcurrencyOverflowPolicy.DROP,
            ),
        )
        with factory() as uow:
            schedule = uow.schedules.get(ScheduleId("shared"))
            assert schedule is not None
            request = ExecutionRequest.from_occurrence(
                occurrence=Occurrence(
                    schedule_id=schedule.id,
                    schedule_revision=ScheduleRevision(1),
                    scheduled_at=at(),
                ),
                target=schedule.definition.target,
                created_at=at(),
                concurrency_policy=schedule.definition.concurrency,
            )
            uow.requests.add(request)
            uow.commit()
        holder = ScheduleAdmissionLockCoordinator(
            uow_factory=factory, worker_id=WorkerId("a"), ttl=Duration.seconds(5)
        )
        assert holder.acquire(schedule_id=ScheduleId("shared"), now=at()).acquired
        contender = Scheduler(
            clock=MutableClock(at()), uow_factory=SqliteUnitOfWorkFactory(db), worker_id="b"
        )
        result = contender.run_pending()
        assert result.admission_lock_denied_request_ids == (request.id,)
        assert result.executions == ()


# 20. observability --------------------------------------------------------
def observability() -> None:
    clock = MutableClock(at())
    sink = InMemoryObservationSink()
    scheduler = Scheduler(clock=clock, observation_sink=sink)
    scheduler.add_schedule(id="obs", target=lambda: None, trigger=every_10())
    clock.advance(Duration.minutes(10))
    scheduler.run_pending()
    attempts = sink.by_name("execution.attempt.completed")
    cycles = sink.by_name("scheduler.cycle.completed")
    assert len(attempts) == 1 and attempts[0].attribute("state") == "success"
    assert cycles and cycles[0].attribute("succeeded") == 1


# 21. operational API ------------------------------------------------------
def operational_api() -> None:
    clock = MutableClock(at())
    scheduler = Scheduler(clock=clock)
    scheduler.add_schedule(id="op", target=lambda: None, trigger=every_10())
    assert scheduler.inspect_schedule("op").state is ScheduleState.ACTIVE
    assert scheduler.pause_schedule("op").state is ScheduleState.PAUSED
    assert scheduler.resume_schedule("op").state is ScheduleState.ACTIVE
    assert scheduler.cancel_schedule("op").state is ScheduleState.CANCELLED
    assert scheduler.health().healthy is True
    assert scheduler.readiness().ready is False
    scheduler.run_pending()
    assert scheduler.readiness().ready is True


# 22. retention / cleanup --------------------------------------------------
def retention() -> None:
    from pyschedulekit import ExecutionNotFoundError

    clock = MutableClock(at())
    scheduler = Scheduler(clock=clock)
    sid = scheduler.add_schedule(id="ret", target=lambda: None, trigger=every_10())
    clock.advance(Duration.minutes(10))
    execution_id = scheduler.run_pending().executions[0].execution.id

    class Publisher:
        def publish(self, message) -> None:
            del message

    scheduler.dispatch_outbox(Publisher(), limit=100)
    clock.advance(Duration.days(31))
    result = scheduler.cleanup(
        RetentionPolicy.days(execution_history=30, published_outbox=30),
        limit=100,
    )
    assert result.execution_graphs_deleted == 1
    try:
        scheduler.inspect_execution(execution_id)
    except ExecutionNotFoundError:
        pass
    else:
        raise AssertionError("execution should have been cleaned up")
    assert scheduler.inspect_schedule(sid).schedule_id == sid


# 23. continuous runtime ---------------------------------------------------
def continuous_runtime() -> None:
    clock = MutableClock(at())
    scheduler = Scheduler(clock=clock)
    called = threading.Event()
    scheduler.add_schedule(id="rt", target=called.set, trigger=every_10())
    worker = threading.Thread(
        target=lambda: scheduler.run_forever(poll_interval=Duration.seconds(0.01))
    )
    worker.start()
    deadline = time.monotonic() + 2
    while scheduler.cycles_completed < 1 and time.monotonic() < deadline:
        time.sleep(0.001)
    clock.advance(Duration.minutes(10))
    assert called.wait(2)
    scheduler.stop()
    worker.join(2)
    assert not worker.is_alive() and scheduler.is_running is False


# 24. graceful shutdown ----------------------------------------------------
def graceful_shutdown() -> None:
    clock = MutableClock(at())
    scheduler = Scheduler(clock=clock)
    started = threading.Event()
    release = threading.Event()

    def target() -> None:
        started.set()
        release.wait(2)

    scheduler.add_schedule(id="sd", target=target, trigger=every_10())
    clock.advance(Duration.minutes(10))
    worker = threading.Thread(target=lambda: scheduler.run_forever(max_sleep=Duration.seconds(30)))
    worker.start()
    assert started.wait(2)
    box: list = []
    stopper = threading.Thread(
        target=lambda: box.append(
            scheduler.shutdown(mode=ShutdownMode.WAIT, timeout=Duration.seconds(1))
        )
    )
    stopper.start()
    time.sleep(0.02)
    release.set()
    stopper.join(2)
    worker.join(2)
    assert box and box[0].completed is True


# 25. mutation-driven wake-up ----------------------------------------------
def wake_up() -> None:
    clock = MutableClock(at())
    scheduler = Scheduler(clock=clock)
    called = threading.Event()
    scheduler.add_schedule(id="w1", target=lambda: None, trigger=every_10())
    scheduler.add_schedule(
        id="w2",
        target=called.set,
        trigger=IntervalTrigger(every=Duration.hours(1), anchor=at(hour=11)),
    )
    worker = threading.Thread(target=lambda: scheduler.run_forever(max_sleep=Duration.seconds(30)))
    worker.start()
    deadline = time.monotonic() + 2
    while scheduler.cycles_completed < 1 and time.monotonic() < deadline:
        time.sleep(0.001)
    clock.advance(Duration.hours(1))
    t0 = time.monotonic()
    scheduler.add_schedule(
        id="w3",
        target=lambda: None,
        trigger=IntervalTrigger(every=Duration.hours(1), anchor=at(hour=12)),
    )
    assert called.wait(2)
    latency = time.monotonic() - t0
    scheduler.stop()
    worker.join(2)
    assert latency < 1.5, latency


# 26. HTTP executor against a live local server ----------------------------
def http_executor_live() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            self.send_response(200 if self.path == "/ok" else 500)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        clock = MutableClock(at())
        scheduler = Scheduler(clock=clock)
        ok = scheduler.register_http_target(
            "ok",
            HttpRequestSpec(
                url=f"http://127.0.0.1:{port}/ok",
                method=HttpMethod.POST,
                body=b"{}",
            ),
        )
        bad = scheduler.register_http_target(
            "bad", HttpRequestSpec(url=f"http://127.0.0.1:{port}/bad")
        )
        scheduler.add_schedule(id="http-ok", target=ok, trigger=every_10())
        scheduler.add_schedule(id="http-bad", target=bad, trigger=every_10())
        clock.advance(Duration.minutes(10))
        result = scheduler.run_pending()
        assert result.succeeded == 1, result
        assert result.failed == 1
    finally:
        server.shutdown()
        server.server_close()


# 27. custom routed executor ----------------------------------------------
@dataclass(frozen=True)
class _Prepared:
    target: TargetRef


class _WorkflowExecutor:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def prepare(self, target: TargetRef) -> PreparedTarget:
        return _Prepared(target)

    def execute(self, prepared: PreparedTarget, **kwargs) -> ExecutorOutcome:
        del kwargs
        self.calls.append(prepared.target.reference)
        return ExecutorOutcome()


def routing_custom_executor() -> None:
    clock = MutableClock(at())
    executor = _WorkflowExecutor()
    scheduler = Scheduler(clock=clock, executors={"workflow": executor})
    scheduler.add_schedule(id="wf", target=TargetRef.workflow("deploy:1"), trigger=every_10())
    clock.advance(Duration.minutes(10))
    assert scheduler.run_pending().succeeded == 1
    assert executor.calls == ["deploy:1"]


# 28. public API contract + deprecation ------------------------------------
def public_api_contract() -> None:
    assert psk.Scheduler is psk.api.Scheduler
    assert psk.Duration is psk.api.Duration
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        legacy = psk.ExecutionClaim  # legacy root name -> experimental redirect
        assert legacy is not None
    assert any(issubclass(w.category, PyScheduleKitDeprecationWarning) for w in caught), caught


# 29. testing helpers ------------------------------------------------------
def testing_helpers() -> None:
    clock = MutableClock(at())
    assert clock.now() == at()
    clock.set(at(hour=12))
    assert clock.now() == at(hour=12)
    clock.advance(Duration.minutes(30))
    assert clock.now() == at(hour=12, minute=30)
    assert FixedClock(at(hour=8)).now() == at(hour=8)


# 30. failure surface ------------------------------------------------------
def failure_surface() -> None:
    from pyschedulekit import ScheduleNotFoundError

    scheduler = Scheduler(clock=MutableClock(at()))
    try:
        scheduler.inspect_schedule("missing")
    except ScheduleNotFoundError:
        pass
    else:
        raise AssertionError("expected ScheduleNotFoundError")

    # a declared-but-unregistered target is reported as a structured error
    scheduler.add_schedule(
        id="missing-target", target=TargetRef.python("nope:none"), trigger=every_10()
    )
    scheduler._clock.advance(Duration.minutes(10))
    result = scheduler.run_pending()
    assert result.errors and result.errors[0].code == "executor.target_resolution", result.errors


CHECKS = [
    ("time_model", time_model),
    ("triggers_date", date_trigger),
    ("triggers_interval", interval_trigger),
    ("triggers_cron", cron_trigger),
    ("schedule_aggregate", schedule_aggregate),
    ("run_pending_local", run_pending_local),
    ("retry_fixed", retry_fixed),
    ("retry_variants", retry_variants),
    ("execution_timeout", execution_timeout),
    ("cancellation_public", cancellation_public),
    ("cancellation_vs_retry", cancellation_vs_retry),
    ("concurrency_limit", concurrency_limit),
    ("misfire_policy", misfire_policy),
    ("sqlite_persistence", sqlite_persistence),
    ("crash_recovery", crash_recovery),
    ("reconciliation", reconciliation),
    ("outbox", outbox),
    ("claims", claims),
    ("admission_lock", admission_lock),
    ("observability", observability),
    ("operational_api", operational_api),
    ("retention", retention),
    ("continuous_runtime", continuous_runtime),
    ("graceful_shutdown", graceful_shutdown),
    ("wake_up", wake_up),
    ("http_executor_live", http_executor_live),
    ("routing_custom_executor", routing_custom_executor),
    ("public_api_contract", public_api_contract),
    ("testing_helpers", testing_helpers),
    ("failure_surface", failure_surface),
]


def main() -> int:
    print(f"pyschedulekit {psk.__version__} — functional exercise")
    print("=" * 70)
    for name, fn in CHECKS:
        run(name, fn)
    print("=" * 70)
    passed = sum(1 for _, status, _ in RESULTS if status == "PASS")
    failed = [(n, d) for n, s, d in RESULTS if s == "FAIL"]
    print(f"{passed}/{len(RESULTS)} checks passed")
    for name, detail in failed:
        print(f"  FAILED: {name}: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
