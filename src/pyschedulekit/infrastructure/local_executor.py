"""Safe registered-callable local executor."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event, Thread

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


class DuplicateTargetRegistrationError(TargetResolutionError):
    """Raised when a registry key is registered more than once."""


class InvalidCallableTargetError(TargetResolutionError):
    """Raised when a callable does not satisfy the local executor contract."""


@dataclass(frozen=True, slots=True)
class RegisteredPythonTarget:
    callable: Callable[..., object]
    accepts_cancellation_token: bool


class PythonTargetRegistry:
    """Explicit registry of trusted Python callables."""

    def __init__(self) -> None:
        self._targets: dict[str, RegisteredPythonTarget] = {}

    def register(self, reference: str, target: Callable[..., object]) -> None:
        if not reference.strip():
            raise InvalidCallableTargetError("Target reference must not be empty.")
        if reference in self._targets:
            raise DuplicateTargetRegistrationError(
                f"Target reference {reference!r} is already registered."
            )
        if inspect.iscoroutinefunction(target):
            raise InvalidCallableTargetError(
                "Async callables are not supported by the synchronous local executor."
            )

        try:
            signature = inspect.signature(target)
        except (TypeError, ValueError) as exc:
            raise InvalidCallableTargetError(
                "Callable signature must be inspectable before registration."
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

        accepts_cancellation_token = False
        if len(required) == 1 and required[0].name == "cancellation_token":
            accepts_cancellation_token = True
        elif required:
            raise InvalidCallableTargetError(
                "Local executor callables must require no arguments or one "
                "'cancellation_token' argument."
            )

        self._targets[reference] = RegisteredPythonTarget(
            callable=target,
            accepts_cancellation_token=accepts_cancellation_token,
        )

    def resolve(self, reference: str) -> RegisteredPythonTarget:
        try:
            return self._targets[reference]
        except KeyError as exc:
            raise TargetResolutionError(f"Python target {reference!r} is not registered.") from exc


@dataclass(frozen=True, slots=True)
class PreparedPythonTarget:
    """Resolved local Python callable ready for invocation."""

    target: TargetRef
    callable: Callable[..., object]
    accepts_cancellation_token: bool


class LocalExecutor:
    """Synchronous executor for explicitly registered trusted Python callables."""

    def __init__(self, *, registry: PythonTargetRegistry, clock: Clock) -> None:
        self._registry = registry
        self._clock = clock

    def prepare(self, target: TargetRef) -> PreparedPythonTarget:
        if target.kind != "python":
            raise UnsupportedTargetError(
                f"LocalExecutor does not support target kind {target.kind!r}."
            )

        registered = self._registry.resolve(target.reference)
        return PreparedPythonTarget(
            target=target,
            callable=registered.callable,
            accepts_cancellation_token=registered.accepts_cancellation_token,
        )

    def execute(
        self,
        prepared: PreparedTarget,
        *,
        timeout: Duration | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> ExecutorOutcome:
        if not isinstance(prepared, PreparedPythonTarget):
            raise TargetResolutionError(
                "LocalExecutor can only execute PreparedPythonTarget values."
            )

        if cancellation_token is not None and cancellation_token.is_cancelled:
            return self._cancelled_outcome()

        if timeout is None:
            outcome = self._invoke(
                prepared,
                cancellation_token=cancellation_token,
            )
            if cancellation_token is not None and cancellation_token.is_cancelled:
                return self._cancelled_outcome()
            return outcome

        if timeout.total_seconds <= 0:
            raise ValueError("Executor timeout must be greater than zero.")

        started_at = self._clock.now()
        completed = Event()
        outcomes: list[ExecutorOutcome] = []
        crashes: list[BaseException] = []

        def invoke() -> None:
            try:
                outcomes.append(
                    self._invoke(
                        prepared,
                        cancellation_token=cancellation_token,
                    )
                )
            except BaseException as exc:
                crashes.append(exc)
            finally:
                completed.set()

        worker = Thread(
            target=invoke,
            name=f"pyschedulekit:{prepared.target.reference}",
            daemon=True,
        )
        worker.start()

        if not completed.wait(timeout.total_seconds):
            return self._timeout_outcome()

        if crashes:
            raise crashes[0]

        outcome = outcomes[0]
        if cancellation_token is not None and cancellation_token.is_cancelled:
            return self._cancelled_outcome()
        elapsed = self._clock.now().elapsed_since(started_at)
        if elapsed >= timeout:
            return self._timeout_outcome()
        return outcome

    def _invoke(
        self,
        prepared: PreparedPythonTarget,
        *,
        cancellation_token: CancellationToken | None,
    ) -> ExecutorOutcome:
        try:
            if prepared.accepts_cancellation_token:
                if cancellation_token is None:
                    raise RuntimeError(
                        "Cancellable target requires a cancellation token."
                    )
                value = prepared.callable(cancellation_token)
            else:
                value = prepared.callable()
        except ExecutionCancelledError:
            return self._cancelled_outcome()
        except Exception as exc:
            return ExecutorOutcome(
                failure=Failure(
                    category=FailureCategory.UNKNOWN,
                    code="python.exception",
                    message="Python target raised an exception.",
                    occurred_at=self._clock.now(),
                    retryable_hint=None,
                    details=(("exception_type", type(exc).__name__),),
                )
            )

        if inspect.isawaitable(value):
            if inspect.iscoroutine(value):
                value.close()
            return ExecutorOutcome(
                failure=Failure(
                    category=FailureCategory.PERMANENT,
                    code="python.async_result_not_supported",
                    message="Python target returned an awaitable in the synchronous executor.",
                    occurred_at=self._clock.now(),
                    retryable_hint=False,
                )
            )

        return ExecutorOutcome()

    def _cancelled_outcome(self) -> ExecutorOutcome:
        occurred_at = self._clock.now()
        return ExecutorOutcome(
            failure=Failure(
                category=FailureCategory.CANCELLED,
                code="execution.cancelled",
                message="Execution attempt was cancelled.",
                occurred_at=occurred_at,
                retryable_hint=False,
            )
        )

    def _timeout_outcome(self) -> ExecutorOutcome:
        occurred_at = self._clock.now()
        return ExecutorOutcome(
            failure=Failure(
                category=FailureCategory.TIMEOUT,
                code="execution.timeout",
                message="Execution attempt timed out.",
                occurred_at=occurred_at,
                retryable_hint=True,
            )
        )
