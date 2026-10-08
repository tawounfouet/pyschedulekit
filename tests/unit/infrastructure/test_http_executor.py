"""LOT-33 unit tests for dependency-free HTTP execution."""

from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from pyschedulekit.domain.execution import FailureCategory
from pyschedulekit.domain.schedule import TargetRef
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.infrastructure.http_executor import (
    DuplicateHttpTargetRegistrationError,
    HttpExecutor,
    HttpMethod,
    HttpRequestSpec,
    HttpTargetRegistry,
)
from pyschedulekit.ports.executor import TargetResolutionError, UnsupportedTargetError
from pyschedulekit.testing import MutableClock


class _Response:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback


class _Token:
    def __init__(self, cancelled: bool = False) -> None:
        self.cancelled = cancelled

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise RuntimeError("cancelled")


def _instant() -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))


def _executor() -> tuple[HttpExecutor, HttpTargetRegistry]:
    registry = HttpTargetRegistry()
    return HttpExecutor(registry=registry, clock=MutableClock(_instant())), registry


def test_t_http_001_request_spec_rejects_unsafe_or_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="http:// or https://"):
        HttpRequestSpec(url="file:///tmp/work")
    with pytest.raises(ValueError, match="credentials"):
        HttpRequestSpec(url="https://user:secret@example.test/hook")
    with pytest.raises(ValueError, match="reserved"):
        HttpRequestSpec(
            url="https://example.test/hook",
            headers=(("Idempotency-Key", "user-value"),),
        )


def test_t_http_002_registry_is_opaque_and_rejects_duplicates() -> None:
    registry = HttpTargetRegistry()
    spec = HttpRequestSpec(url="https://example.test/hook")
    registry.register("notify", spec)

    assert registry.resolve("notify") == spec
    with pytest.raises(DuplicateHttpTargetRegistrationError):
        registry.register("notify", spec)
    with pytest.raises(TargetResolutionError, match="not registered"):
        registry.resolve("missing")


def test_t_http_003_prepare_rejects_non_http_target() -> None:
    executor, _ = _executor()

    with pytest.raises(UnsupportedTargetError):
        executor.prepare(TargetRef.python("job"))


def test_t_http_004_success_propagates_execution_metadata(monkeypatch) -> None:
    executor, registry = _executor()
    registry.register(
        "notify",
        HttpRequestSpec(
            url="https://example.test/hook",
            method=HttpMethod.POST,
            headers=(("X-App", "scheduler"),),
            body=b"{}",
        ),
    )
    observed: list[Request] = []

    def fake_urlopen(request, timeout=None):
        del timeout
        observed.append(request)
        return _Response(204)

    monkeypatch.setattr(
        "pyschedulekit.infrastructure.http_executor.urlopen",
        fake_urlopen,
    )

    outcome = executor.execute(
        executor.prepare(TargetRef.http("notify")),
        timeout=Duration.seconds(3),
        fencing_token=9,
        idempotency_key="idem-9",
    )

    assert outcome.succeeded
    headers = {name.lower(): value for name, value in observed[0].header_items()}
    assert headers["idempotency-key"] == "idem-9"
    assert headers["x-pyschedulekit-fencing-token"] == "9"
    assert headers["x-app"] == "scheduler"


@pytest.mark.parametrize(
    ("status", "category", "retryable"),
    [
        (400, FailureCategory.PERMANENT, False),
        (404, FailureCategory.PERMANENT, False),
        (408, FailureCategory.TRANSIENT, True),
        (429, FailureCategory.TRANSIENT, True),
        (503, FailureCategory.TRANSIENT, True),
    ],
)
def test_t_http_005_status_classification(
    monkeypatch,
    status: int,
    category: FailureCategory,
    retryable: bool,
) -> None:
    executor, registry = _executor()
    registry.register("notify", HttpRequestSpec(url="https://example.test/hook"))

    def failing_urlopen(request, timeout=None):
        del timeout
        raise HTTPError(request.full_url, status, "failure", None, None)

    monkeypatch.setattr(
        "pyschedulekit.infrastructure.http_executor.urlopen",
        failing_urlopen,
    )

    outcome = executor.execute(executor.prepare(TargetRef.http("notify")))

    assert outcome.failure is not None
    assert outcome.failure.category is category
    assert outcome.failure.retryable_hint is retryable
    assert outcome.failure.details == (("status_code", str(status)),)


def test_t_http_006_transport_and_timeout_are_retryable(monkeypatch) -> None:
    executor, registry = _executor()
    registry.register("notify", HttpRequestSpec(url="https://example.test/hook"))

    def unreachable(request, timeout=None):
        del request, timeout
        raise URLError("connection refused")

    monkeypatch.setattr(
        "pyschedulekit.infrastructure.http_executor.urlopen",
        unreachable,
    )
    transport = executor.execute(executor.prepare(TargetRef.http("notify")))
    assert transport.failure is not None
    assert transport.failure.category is FailureCategory.TRANSIENT
    assert transport.failure.retryable_hint is True

    def timed_out(request, timeout=None):
        del request, timeout
        raise TimeoutError

    monkeypatch.setattr(
        "pyschedulekit.infrastructure.http_executor.urlopen",
        timed_out,
    )
    timeout = executor.execute(executor.prepare(TargetRef.http("notify")))
    assert timeout.failure is not None
    assert timeout.failure.category is FailureCategory.TIMEOUT
    assert timeout.failure.retryable_hint is True


def test_t_http_007_pre_cancelled_request_never_performs_io(monkeypatch) -> None:
    executor, registry = _executor()
    registry.register("notify", HttpRequestSpec(url="https://example.test/hook"))

    def should_not_run(request, timeout=None):
        del request, timeout
        raise AssertionError("HTTP I/O should not run")

    monkeypatch.setattr(
        "pyschedulekit.infrastructure.http_executor.urlopen",
        should_not_run,
    )

    outcome = executor.execute(
        executor.prepare(TargetRef.http("notify")),
        cancellation_token=_Token(cancelled=True),
    )

    assert outcome.failure is not None
    assert outcome.failure.category is FailureCategory.CANCELLED
