"""POST-00F regression tests for HTTP resource and redirect hardening."""

from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from pyschedulekit.domain.execution import FailureCategory
from pyschedulekit.domain.schedule import TargetRef
from pyschedulekit.domain.time import Instant
from pyschedulekit.infrastructure.http_executor import (
    HttpExecutor,
    HttpRequestSpec,
    HttpTargetRegistry,
    _ControlledRedirectHandler,
)
from pyschedulekit.testing import FixedClock


def _instant() -> Instant:
    from datetime import UTC, datetime

    return Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))


def _executor() -> tuple[HttpExecutor, HttpTargetRegistry]:
    registry = HttpTargetRegistry()
    return HttpExecutor(registry=registry, clock=FixedClock(_instant())), registry


class _CloseTracker:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_http_error_response_is_closed_before_outcome_returns(monkeypatch) -> None:
    executor, registry = _executor()
    registry.register("notify", HttpRequestSpec(url="https://example.test/hook"))
    response_body = BytesIO(b"failure")

    def failing_open(request: Request, timeout: float | None = None):
        del timeout
        raise HTTPError(
            request.full_url,
            503,
            "unavailable",
            None,
            response_body,
        )

    monkeypatch.setattr(
        "pyschedulekit.infrastructure.http_executor._open_http_request",
        failing_open,
    )

    outcome = executor.execute(executor.prepare(TargetRef.http("notify")))

    assert outcome.failure is not None
    assert outcome.failure.category is FailureCategory.TRANSIENT
    assert response_body.closed is True


@pytest.mark.parametrize(
    "redirect_url",
    (
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "https://user:secret@example.test/private",
    ),
)
def test_unsafe_redirect_is_blocked_and_response_is_closed(redirect_url: str) -> None:
    handler = _ControlledRedirectHandler("example.test")
    response = _CloseTracker()

    with pytest.raises(URLError, match="Blocked HTTP redirect"):
        handler.redirect_request(
            Request("https://example.test/start"),
            response,
            302,
            "Found",
            None,
            redirect_url,
        )

    assert response.closed is True


def test_same_host_redirects_are_bounded_to_three_hops() -> None:
    handler = _ControlledRedirectHandler("example.test")
    request = Request("https://example.test/start")

    for hop in range(3):
        redirected = handler.redirect_request(
            request,
            _CloseTracker(),
            302,
            "Found",
            None,
            f"https://example.test/hop-{hop + 1}",
        )
        assert redirected is not None
        assert redirected.full_url == f"https://example.test/hop-{hop + 1}"

    blocked_response = _CloseTracker()
    with pytest.raises(URLError, match="maximum redirect count"):
        handler.redirect_request(
            request,
            blocked_response,
            302,
            "Found",
            None,
            "https://example.test/hop-4",
        )

    assert blocked_response.closed is True
