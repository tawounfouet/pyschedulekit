"""LOT-33 end-to-end qualification for routed HTTP and custom executors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.error import HTTPError

from pyschedulekit import (
    Duration,
    HttpRequestSpec,
    InMemoryObservationSink,
    Instant,
    IntervalTrigger,
    RetryPolicy,
    Scheduler,
    TargetRef,
)
from pyschedulekit.domain.execution import ExecutionState
from pyschedulekit.domain.time import Duration as DomainDuration
from pyschedulekit.ports.cancellation import CancellationToken
from pyschedulekit.ports.executor import ExecutorOutcome, PreparedTarget
from pyschedulekit.testing import MutableClock


class _Response:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback


@dataclass(frozen=True, slots=True)
class _WorkflowPrepared:
    target: TargetRef


class _WorkflowExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None, str | None]] = []

    def prepare(self, target: TargetRef) -> PreparedTarget:
        return _WorkflowPrepared(target)

    def execute(
        self,
        prepared: PreparedTarget,
        *,
        timeout: DomainDuration | None = None,
        cancellation_token: CancellationToken | None = None,
        fencing_token: int | None = None,
        idempotency_key: str | None = None,
    ) -> ExecutorOutcome:
        del timeout, cancellation_token
        self.calls.append((prepared.target.reference, fencing_token, idempotency_key))
        return ExecutorOutcome()


def _instant() -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))


def _trigger() -> IntervalTrigger:
    return IntervalTrigger(
        every=Duration.minutes(10),
        anchor=_instant().add(Duration.minutes(10)),
    )


def test_t_executor_e2e_001_http_runs_through_public_scheduler(monkeypatch) -> None:
    clock = MutableClock(_instant())
    sink = InMemoryObservationSink()
    scheduler = Scheduler(clock=clock, observation_sink=sink)
    observed_headers: list[dict[str, str]] = []

    target = scheduler.register_http_target(
        "notify",
        HttpRequestSpec(url="https://example.test/hooks/notify"),
    )

    def fake_urlopen(request, timeout=None):
        del timeout
        observed_headers.append({name.lower(): value for name, value in request.header_items()})
        return _Response(204)

    monkeypatch.setattr(
        "pyschedulekit.infrastructure.http_executor.urlopen",
        fake_urlopen,
    )

    scheduler.add_schedule(
        id="http-notify",
        target=target,
        trigger=_trigger(),
    )
    clock.advance(Duration.minutes(10))

    result = scheduler.run_pending()

    assert result.succeeded == 1
    assert result.executions[0].execution.state is ExecutionState.SUCCESS
    assert observed_headers[0]["idempotency-key"]
    assert observed_headers[0]["x-pyschedulekit-fencing-token"] == "1"

    attempt_observation = sink.by_name("execution.attempt.completed")[-1]
    assert dict(attempt_observation.attributes)["target_kind"] == "http"


def test_t_executor_e2e_002_http_transient_failure_uses_retry_policy(monkeypatch) -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    target = scheduler.register_http_target(
        "retry-http",
        HttpRequestSpec(url="https://example.test/retry"),
    )
    calls = 0

    def flaky_urlopen(request, timeout=None):
        nonlocal calls
        del timeout
        calls += 1
        if calls == 1:
            raise HTTPError(request.full_url, 503, "unavailable", None, None)
        return _Response(200)

    monkeypatch.setattr(
        "pyschedulekit.infrastructure.http_executor.urlopen",
        flaky_urlopen,
    )

    scheduler.add_schedule(
        id="http-retry",
        target=target,
        trigger=_trigger(),
        retry=RetryPolicy(max_attempts=2),
    )
    clock.advance(Duration.minutes(10))

    first = scheduler.run_pending()
    second = scheduler.run_pending()

    assert first.executions[0].execution.state is ExecutionState.RETRY_WAIT
    assert second.executions[0].execution.state is ExecutionState.SUCCESS
    assert calls == 2


def test_t_executor_e2e_003_custom_workflow_executor_uses_same_pipeline() -> None:
    clock = MutableClock(_instant())
    workflow = _WorkflowExecutor()
    scheduler = Scheduler(
        clock=clock,
        executors={"workflow": workflow},
    )

    scheduler.add_schedule(
        id="workflow-job",
        target=TargetRef.workflow("daily-close"),
        trigger=_trigger(),
    )
    clock.advance(Duration.minutes(10))

    result = scheduler.run_pending()

    assert result.succeeded == 1
    assert workflow.calls[0][0] == "daily-close"
    assert workflow.calls[0][1] == 1
    assert workflow.calls[0][2] is not None
