"""Dependency-free HTTP executor with explicit target registration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import ParseResult, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pyschedulekit.domain.execution import Failure, FailureCategory
from pyschedulekit.domain.schedule import TargetRef
from pyschedulekit.domain.time import Duration
from pyschedulekit.errors import PyScheduleKitConfigurationError
from pyschedulekit.ports.cancellation import CancellationToken
from pyschedulekit.ports.executor import (
    ExecutorOutcome,
    PreparedTarget,
    TargetResolutionError,
    UnsupportedTargetError,
)
from pyschedulekit.ports.time import Clock

_IDEMPOTENCY_HEADER = "Idempotency-Key"
_FENCING_HEADER = "X-PyScheduleKit-Fencing-Token"
_MAX_REDIRECTS = 3
_RESERVED_HEADERS = frozenset(
    {
        _IDEMPOTENCY_HEADER.lower(),
        _FENCING_HEADER.lower(),
    }
)


def _validate_http_url(url: str) -> ParseResult:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise PyScheduleKitConfigurationError(
            "HTTP executor URL must use http:// or https:// with a host."
        )
    if parsed.username is not None or parsed.password is not None:
        raise PyScheduleKitConfigurationError("HTTP executor URL must not embed credentials.")
    return parsed


class _ControlledRedirectHandler(HTTPRedirectHandler):
    """Allow only bounded same-host HTTP(S) redirects."""

    def __init__(self, allowed_host: str) -> None:
        super().__init__()
        self._allowed_host = allowed_host.casefold()
        self._hops = 0

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        self._hops += 1
        try:
            redirected = _validate_http_url(newurl)
            if self._hops > _MAX_REDIRECTS:
                raise URLError("Blocked HTTP redirect: maximum redirect count exceeded.")
            if redirected.hostname is None or redirected.hostname.casefold() != self._allowed_host:
                raise URLError("Blocked HTTP redirect: destination host changed.")
        except (PyScheduleKitConfigurationError, URLError) as exc:
            try:
                fp.close()
            finally:
                if isinstance(exc, URLError):
                    raise
                raise URLError("Blocked HTTP redirect: destination URL is not allowed.") from exc

        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_http_request(request: Request, timeout: float | None = None) -> Any:
    parsed = _validate_http_url(request.full_url)
    assert parsed.hostname is not None
    opener = build_opener(_ControlledRedirectHandler(parsed.hostname))
    return opener.open(request, timeout=timeout)


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"


@dataclass(frozen=True, slots=True)
class HttpRequestSpec:
    """Trusted HTTP request definition resolved from an opaque TargetRef."""

    url: str
    method: HttpMethod = HttpMethod.POST
    headers: tuple[tuple[str, str], ...] = ()
    body: bytes | None = None

    def __post_init__(self) -> None:
        _validate_http_url(self.url)

        seen: set[str] = set()
        for name, value in self.headers:
            normalized = name.strip().lower()
            if not normalized:
                raise PyScheduleKitConfigurationError("HTTP header name must not be empty.")
            if normalized in seen:
                raise PyScheduleKitConfigurationError(f"Duplicate HTTP header: {name!r}.")
            if normalized in _RESERVED_HEADERS:
                raise PyScheduleKitConfigurationError(
                    f"HTTP header {name!r} is reserved for scheduler execution metadata."
                )
            if "\r" in name or "\n" in name or "\r" in value or "\n" in value:
                raise PyScheduleKitConfigurationError(
                    "HTTP headers must not contain CR/LF characters."
                )
            seen.add(normalized)


class DuplicateHttpTargetRegistrationError(TargetResolutionError):
    """Raised when an HTTP target reference is registered twice."""


class HttpTargetRegistry:
    """Process-local registry mapping opaque references to trusted HTTP requests."""

    def __init__(self) -> None:
        self._targets: dict[str, HttpRequestSpec] = {}

    def register(self, reference: str, request: HttpRequestSpec) -> None:
        if not reference.strip():
            raise PyScheduleKitConfigurationError("HTTP target reference must not be empty.")
        if reference in self._targets:
            raise DuplicateHttpTargetRegistrationError(
                f"HTTP target reference {reference!r} is already registered."
            )
        self._targets[reference] = request

    def resolve(self, reference: str) -> HttpRequestSpec:
        try:
            return self._targets[reference]
        except KeyError as exc:
            raise TargetResolutionError(f"HTTP target {reference!r} is not registered.") from exc


@dataclass(frozen=True, slots=True)
class PreparedHttpTarget:
    """Resolved HTTP target ready for invocation."""

    target: TargetRef
    request: HttpRequestSpec


class HttpExecutor:
    """Invoke explicitly registered HTTP endpoints through Python's standard library."""

    def __init__(self, *, registry: HttpTargetRegistry, clock: Clock) -> None:
        self._registry = registry
        self._clock = clock

    def prepare(self, target: TargetRef) -> PreparedHttpTarget:
        if target.kind != "http":
            raise UnsupportedTargetError(
                f"HttpExecutor does not support target kind {target.kind!r}."
            )
        return PreparedHttpTarget(
            target=target,
            request=self._registry.resolve(target.reference),
        )

    def execute(
        self,
        prepared: PreparedTarget,
        *,
        timeout: Duration | None = None,
        cancellation_token: CancellationToken | None = None,
        fencing_token: int | None = None,
        idempotency_key: str | None = None,
    ) -> ExecutorOutcome:
        if not isinstance(prepared, PreparedHttpTarget):
            raise TargetResolutionError("HttpExecutor can only execute PreparedHttpTarget values.")
        if timeout is not None and timeout.total_seconds <= 0:
            raise PyScheduleKitConfigurationError("Executor timeout must be greater than zero.")
        if cancellation_token is not None and cancellation_token.is_cancelled:
            return self._cancelled_outcome()

        headers = dict(prepared.request.headers)
        if idempotency_key is not None:
            headers[_IDEMPOTENCY_HEADER] = idempotency_key
        if fencing_token is not None:
            headers[_FENCING_HEADER] = str(fencing_token)

        request = Request(
            prepared.request.url,
            data=prepared.request.body,
            headers=headers,
            method=prepared.request.method.value,
        )

        timeout_seconds = None if timeout is None else timeout.total_seconds
        try:
            with _open_http_request(request, timeout=timeout_seconds) as response:
                status = int(response.status)
        except HTTPError as exc:
            try:
                status = int(exc.code)
            finally:
                exc.close()
            return self._http_status_outcome(status)
        except TimeoutError:
            return self._timeout_outcome()
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                return self._timeout_outcome()
            return self._transport_outcome()
        except OSError:
            return self._transport_outcome()

        if cancellation_token is not None and cancellation_token.is_cancelled:
            return self._cancelled_outcome()
        if 200 <= status < 300:
            return ExecutorOutcome()
        return self._http_status_outcome(status)

    def _http_status_outcome(self, status: int) -> ExecutorOutcome:
        retryable = status in {408, 425, 429} or status >= 500
        return ExecutorOutcome(
            failure=Failure(
                category=(FailureCategory.TRANSIENT if retryable else FailureCategory.PERMANENT),
                code=f"http.status.{status}",
                message="HTTP target returned a non-success status.",
                occurred_at=self._clock.now(),
                retryable_hint=retryable,
                details=(("status_code", str(status)),),
            )
        )

    def _transport_outcome(self) -> ExecutorOutcome:
        return ExecutorOutcome(
            failure=Failure(
                category=FailureCategory.TRANSIENT,
                code="http.transport",
                message="HTTP target could not be reached.",
                occurred_at=self._clock.now(),
                retryable_hint=True,
            )
        )

    def _timeout_outcome(self) -> ExecutorOutcome:
        return ExecutorOutcome(
            failure=Failure(
                category=FailureCategory.TIMEOUT,
                code="execution.timeout",
                message="HTTP target timed out.",
                occurred_at=self._clock.now(),
                retryable_hint=True,
            )
        )

    def _cancelled_outcome(self) -> ExecutorOutcome:
        return ExecutorOutcome(
            failure=Failure(
                category=FailureCategory.CANCELLED,
                code="execution.cancelled",
                message="HTTP execution was cancelled.",
                occurred_at=self._clock.now(),
                retryable_hint=False,
            )
        )
