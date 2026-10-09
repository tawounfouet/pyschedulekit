"""LOT-10 unit tests for registered-callable local execution."""

from datetime import UTC, datetime
from threading import Event, Thread

import pytest

from pyschedulekit.domain.execution import FailureCategory
from pyschedulekit.domain.schedule import TargetRef
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.infrastructure.cancellation import InMemoryCancellationController
from pyschedulekit.infrastructure.local_executor import (
    DuplicateTargetRegistrationError,
    InvalidCallableTargetError,
    LocalExecutor,
    PythonTargetRegistry,
)
from pyschedulekit.ports.cancellation import CancellationToken
from pyschedulekit.ports.executor import TargetResolutionError, UnsupportedTargetError
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def test_registry_resolves_explicitly_registered_callable() -> None:
    registry = PythonTargetRegistry()

    def target() -> None:
        return None

    registry.register("refresh", target)

    assert registry.resolve("refresh") is target


def test_registry_rejects_duplicate_reference() -> None:
    registry = PythonTargetRegistry()
    registry.register("refresh", lambda: None)

    with pytest.raises(DuplicateTargetRegistrationError):
        registry.register("refresh", lambda: None)


def test_registry_rejects_empty_reference() -> None:
    registry = PythonTargetRegistry()

    with pytest.raises(InvalidCallableTargetError):
        registry.register("   ", lambda: None)


def test_registry_rejects_callable_with_required_arguments() -> None:
    registry = PythonTargetRegistry()

    def target(customer_id: str) -> None:
        del customer_id

    with pytest.raises(InvalidCallableTargetError, match="must not require arguments"):
        registry.register("refresh", target)


def test_registry_rejects_async_callable() -> None:
    registry = PythonTargetRegistry()

    async def target() -> None:
        return None

    with pytest.raises(InvalidCallableTargetError, match="Async callables"):
        registry.register("refresh", target)


def test_unregistered_reference_is_resolution_error() -> None:
    registry = PythonTargetRegistry()

    with pytest.raises(TargetResolutionError, match="not registered"):
        registry.resolve("missing")


def test_local_executor_rejects_non_python_target_before_invocation() -> None:
    executor = LocalExecutor(
        registry=PythonTargetRegistry(),
        clock=MutableClock(_instant()),
    )

    with pytest.raises(UnsupportedTargetError):
        executor.prepare(TargetRef.workflow("workflow-1"))


def test_local_executor_successfully_invokes_registered_callable() -> None:
    registry = PythonTargetRegistry()
    calls: list[str] = []
    registry.register("refresh", lambda: calls.append("called"))
    executor = LocalExecutor(
        registry=registry,
        clock=MutableClock(_instant()),
    )

    prepared = executor.prepare(TargetRef.python("refresh"))
    outcome = executor.execute(prepared)

    assert outcome.succeeded
    assert outcome.failure is None
    assert calls == ["called"]


def test_target_exception_is_normalized_without_raw_exception_message() -> None:
    registry = PythonTargetRegistry()
    clock = MutableClock(_instant(hour=10, minute=2))

    def target() -> None:
        raise RuntimeError("database password=secret")

    registry.register("refresh", target)
    executor = LocalExecutor(registry=registry, clock=clock)

    outcome = executor.execute(executor.prepare(TargetRef.python("refresh")))

    assert not outcome.succeeded
    assert outcome.failure is not None
    assert outcome.failure.category is FailureCategory.UNKNOWN
    assert outcome.failure.code == "python.exception"
    assert outcome.failure.occurred_at == clock.now()
    assert outcome.failure.details == (("exception_type", "RuntimeError"),)
    assert "secret" not in outcome.failure.message
    assert "secret" not in repr(outcome.failure.details)


def test_local_executor_does_not_catch_base_exception() -> None:
    registry = PythonTargetRegistry()

    def target() -> None:
        raise KeyboardInterrupt

    registry.register("interrupt", target)
    executor = LocalExecutor(
        registry=registry,
        clock=MutableClock(_instant()),
    )

    with pytest.raises(KeyboardInterrupt):
        executor.execute(executor.prepare(TargetRef.python("interrupt")))


def test_sync_callable_returning_awaitable_becomes_permanent_failure() -> None:
    registry = PythonTargetRegistry()

    async def asynchronous_work() -> None:
        return None

    def wrapper() -> object:
        return asynchronous_work()

    registry.register("wrapped-async", wrapper)
    executor = LocalExecutor(
        registry=registry,
        clock=MutableClock(_instant()),
    )

    outcome = executor.execute(executor.prepare(TargetRef.python("wrapped-async")))

    assert outcome.failure is not None
    assert outcome.failure.category is FailureCategory.PERMANENT
    assert outcome.failure.code == "python.async_result_not_supported"


def test_callable_return_value_is_not_interpreted_as_scheduler_state() -> None:
    registry = PythonTargetRegistry()
    registry.register("returns-value", lambda: {"business": "value"})
    executor = LocalExecutor(
        registry=registry,
        clock=MutableClock(_instant()),
    )

    outcome = executor.execute(executor.prepare(TargetRef.python("returns-value")))

    assert outcome.succeeded


def test_local_executor_injects_fencing_token_when_requested() -> None:
    registry = PythonTargetRegistry()
    observed: list[int] = []

    def target(fencing_token: int) -> None:
        observed.append(fencing_token)

    registry.register("fenced", target)
    executor = LocalExecutor(
        registry=registry,
        clock=MutableClock(_instant()),
    )

    outcome = executor.execute(
        executor.prepare(TargetRef.python("fenced")),
        fencing_token=7,
    )

    assert outcome.succeeded
    assert observed == [7]


def test_local_executor_timeout_normalizes_requested_cancellation() -> None:
    """LOT-17: a requested cancellation wins even when the timeout path fires."""

    registry = PythonTargetRegistry()
    started = Event()
    release = Event()

    def target(cancellation_token: CancellationToken) -> None:
        del cancellation_token
        started.set()
        release.wait(1)  # ignores cancellation on purpose

    registry.register("slow", target)
    executor = LocalExecutor(registry=registry, clock=MutableClock(_instant()))
    controller = InMemoryCancellationController()
    token = controller.token_for("execution-1")
    prepared = executor.prepare(TargetRef.python("slow"))

    outcomes: list[object] = []
    worker = Thread(
        target=lambda: outcomes.append(
            executor.execute(
                prepared,
                timeout=Duration.seconds(0.1),
                cancellation_token=token,
            )
        )
    )
    worker.start()
    assert started.wait(1)

    controller.cancel("execution-1")
    worker.join(2)
    release.set()

    assert not worker.is_alive()
    outcome = outcomes[0]
    assert outcome.failure is not None
    assert outcome.failure.category is FailureCategory.CANCELLED


def test_registry_unregister_removes_exact_callable_and_capabilities() -> None:
    registry = PythonTargetRegistry()

    def target(
        cancellation_token: CancellationToken,
        fencing_token: int,
    ) -> None:
        del cancellation_token, fencing_token

    registry.register("refresh", target)

    assert registry.accepts_cancellation_token("refresh")
    assert registry.accepts_fencing_token("refresh")
    assert registry.unregister("refresh", target)

    with pytest.raises(TargetResolutionError, match="not registered"):
        registry.resolve("refresh")

    assert not registry.accepts_cancellation_token("refresh")
    assert not registry.accepts_fencing_token("refresh")


def test_registry_unregister_does_not_remove_a_different_callable() -> None:
    registry = PythonTargetRegistry()

    def registered() -> None:
        return None

    def other() -> None:
        return None

    registry.register("refresh", registered)

    assert not registry.unregister("refresh", other)
    assert registry.resolve("refresh") is registered
