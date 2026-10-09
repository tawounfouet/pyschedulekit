"""Async Python workload adapter behind the synchronous Executor port."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from threading import Thread
from typing import cast

from pyschedulekit.domain.execution import Failure, FailureCategory
from pyschedulekit.domain.schedule import TargetRef
from pyschedulekit.domain.time import Duration
from pyschedulekit.ports.cancellation import CancellationToken, ExecutionCancelledError
from pyschedulekit.ports.executor import (
    ExecutorOutcome,
    PreparedTarget,
    TargetResolutionError,
    UnsupportedTargetError,
)
from pyschedulekit.ports.time import Clock

AsyncCallable = Callable[..., Awaitable[object]]


class DuplicateAsyncTargetRegistrationError(TargetResolutionError):
    """Raised when an async registry key is registered more than once."""


class InvalidAsyncCallableTargetError(TargetResolutionError):
    """Raised when a callable does not satisfy the async executor contract."""


class AsyncPythonTargetRegistry:
    """Explicit registry of trusted async Python callables."""

    def __init__(self) -> None:
        self._targets: dict[str, AsyncCallable] = {}
        self._cancellable_targets: set[str] = set()
        self._fenced_targets: set[str] = set()

    def register(self, reference: str, target: Callable[..., object]) -> None:
        if not reference.strip():
            raise InvalidAsyncCallableTargetError("Target reference must not be empty.")
        if reference in self._targets:
            raise DuplicateAsyncTargetRegistrationError(
                f"Async target reference {reference!r} is already registered."
            )
        if not inspect.iscoroutinefunction(target):
            raise InvalidAsyncCallableTargetError(
                "Async executor targets must be declared with 'async def'."
            )

        try:
            signature = inspect.signature(target)
        except (TypeError, ValueError) as exc:
            raise InvalidAsyncCallableTargetError(
                "Async callable signature must be inspectable before registration."
            ) from exc

        required = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.default is inspect.Parameter.empty
            and parameter.kind
            not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            )
        ]
        supported = {"cancellation_token", "fencing_token"}
        unsupported_required = [
            parameter for parameter in required if parameter.name not in supported
        ]
        if unsupported_required:
            raise InvalidAsyncCallableTargetError(
                "Async executor callables must not require arguments other than "
                "'cancellation_token' and/or 'fencing_token'."
            )

        self._targets[reference] = cast(AsyncCallable, target)
        if "cancellation_token" in signature.parameters:
            self._cancellable_targets.add(reference)
        if "fencing_token" in signature.parameters:
            self._fenced_targets.add(reference)

    def unregister(
        self,
        reference: str,
        target: Callable[..., object],
    ) -> bool:
        registered = self._targets.get(reference)
        if registered is not target:
            return False

        del self._targets[reference]
        self._cancellable_targets.discard(reference)
        self._fenced_targets.discard(reference)
        return True

    def resolve(self, reference: str) -> AsyncCallable:
        try:
            return self._targets[reference]
        except KeyError as exc:
            raise TargetResolutionError(
                f"Async Python target {reference!r} is not registered."
            ) from exc

    def accepts_cancellation_token(self, reference: str) -> bool:
        return reference in self._cancellable_targets

    def accepts_fencing_token(self, reference: str) -> bool:
        return reference in self._fenced_targets


@dataclass(frozen=True, slots=True)
class PreparedAsyncPythonTarget:
    """Resolved async Python callable ready for invocation."""

    target: TargetRef
    callable: AsyncCallable
    accepts_cancellation_token: bool
    accepts_fencing_token: bool


class AsyncioExecutor:
    """Execute trusted async Python callables without asyncifying Scheduler internals.

    Each execution owns an asyncio event loop inside a dedicated worker thread. This keeps
    the synchronous Executor port valid even when Scheduler.run_pending() is called from a
    thread that already owns a running event loop.
    """

    def __init__(self, *, registry: AsyncPythonTargetRegistry, clock: Clock) -> None:
        self._registry = registry
        self._clock = clock

    def prepare(self, target: TargetRef) -> PreparedAsyncPythonTarget:
        if target.kind != "python_async":
            raise UnsupportedTargetError(
                f"AsyncioExecutor does not support target kind {target.kind!r}."
            )

        callable_target = self._registry.resolve(target.reference)
        return PreparedAsyncPythonTarget(
            target=target,
            callable=callable_target,
            accepts_cancellation_token=self._registry.accepts_cancellation_token(target.reference),
            accepts_fencing_token=self._registry.accepts_fencing_token(target.reference),
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
        del idempotency_key

        if not isinstance(prepared, PreparedAsyncPythonTarget):
            raise TargetResolutionError(
                "AsyncioExecutor can only execute PreparedAsyncPythonTarget values."
            )

        if cancellation_token is not None and cancellation_token.is_cancelled:
            return self._cancelled_outcome()

        if timeout is not None and timeout.total_seconds <= 0:
            raise ValueError("Executor timeout must be greater than zero.")

        outcomes: list[ExecutorOutcome] = []
        crashes: list[BaseException] = []

        def run_async() -> None:
            try:
                outcomes.append(
                    asyncio.run(
                        self._invoke(
                            prepared,
                            timeout=timeout,
                            cancellation_token=cancellation_token,
                            fencing_token=fencing_token,
                        )
                    )
                )
            except BaseException as exc:
                crashes.append(exc)

        worker = Thread(
            target=run_async,
            name=f"pyschedulekit-async:{prepared.target.reference}",
            daemon=True,
        )
        worker.start()
        worker.join()

        if crashes:
            raise crashes[0]

        outcome = outcomes[0]
        if cancellation_token is not None and cancellation_token.is_cancelled:
            return self._cancelled_outcome()
        return outcome

    async def _invoke(
        self,
        prepared: PreparedAsyncPythonTarget,
        *,
        timeout: Duration | None,
        cancellation_token: CancellationToken | None,
        fencing_token: int | None,
    ) -> ExecutorOutcome:
        async def call_target() -> ExecutorOutcome:
            try:
                kwargs: dict[str, object] = {}
                if prepared.accepts_cancellation_token:
                    if cancellation_token is None:
                        raise RuntimeError(
                            "Cancellable async target requires a cancellation token."
                        )
                    kwargs["cancellation_token"] = cancellation_token
                if prepared.accepts_fencing_token:
                    if fencing_token is None:
                        raise RuntimeError("Fenced async target requires a fencing token.")
                    kwargs["fencing_token"] = fencing_token

                await prepared.callable(**kwargs)
            except ExecutionCancelledError:
                return self._cancelled_outcome()
            except Exception as exc:
                return ExecutorOutcome(
                    failure=Failure(
                        category=FailureCategory.UNKNOWN,
                        code="python_async.exception",
                        message="Async Python target raised an exception.",
                        occurred_at=self._clock.now(),
                        retryable_hint=None,
                        details=(("exception_type", type(exc).__name__),),
                    )
                )

            return ExecutorOutcome()

        if timeout is None:
            try:
                return await call_target()
            except asyncio.CancelledError:
                return self._cancelled_outcome()

        try:
            return await asyncio.wait_for(
                call_target(),
                timeout=timeout.total_seconds,
            )
        except TimeoutError:
            if cancellation_token is not None and cancellation_token.is_cancelled:
                return self._cancelled_outcome()
            return self._timeout_outcome()
        except asyncio.CancelledError:
            return self._cancelled_outcome()

    def _cancelled_outcome(self) -> ExecutorOutcome:
        return ExecutorOutcome(
            failure=Failure(
                category=FailureCategory.CANCELLED,
                code="execution.cancelled",
                message="Execution attempt was cancelled.",
                occurred_at=self._clock.now(),
                retryable_hint=False,
            )
        )

    def _timeout_outcome(self) -> ExecutorOutcome:
        return ExecutorOutcome(
            failure=Failure(
                category=FailureCategory.TIMEOUT,
                code="execution.timeout",
                message="Execution attempt timed out.",
                occurred_at=self._clock.now(),
                retryable_hint=True,
            )
        )
