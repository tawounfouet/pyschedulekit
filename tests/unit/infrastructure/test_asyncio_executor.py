"""Unit qualification for async Python execution."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.execution import FailureCategory
from pyschedulekit.domain.schedule import TargetRef
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.infrastructure.asyncio_executor import (
    AsyncioExecutor,
    AsyncPythonTargetRegistry,
    DuplicateAsyncTargetRegistrationError,
    InvalidAsyncCallableTargetError,
)
from pyschedulekit.infrastructure.cancellation import InMemoryCancellationController
from pyschedulekit.ports.cancellation import CancellationToken
from pyschedulekit.ports.executor import TargetResolutionError, UnsupportedTargetError
from pyschedulekit.testing import MutableClock


def _instant() -> Instant:
    return Instant(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))


def _executor(
    registry: AsyncPythonTargetRegistry,
) -> AsyncioExecutor:
    return AsyncioExecutor(
        registry=registry,
        clock=MutableClock(_instant()),
    )


def test_async_registry_resolves_explicit_coroutine_function() -> None:
    registry = AsyncPythonTargetRegistry()

    async def target() -> None:
        return None

    registry.register("refresh", target)

    assert registry.resolve("refresh") is target


def test_async_registry_rejects_sync_callable() -> None:
    registry = AsyncPythonTargetRegistry()

    with pytest.raises(InvalidAsyncCallableTargetError, match="async def"):
        registry.register("refresh", lambda: None)


def test_async_registry_rejects_duplicate_and_empty_reference() -> None:
    registry = AsyncPythonTargetRegistry()

    async def target() -> None:
        return None

    registry.register("refresh", target)

    with pytest.raises(DuplicateAsyncTargetRegistrationError):
        registry.register("refresh", target)

    with pytest.raises(InvalidAsyncCallableTargetError, match="must not be empty"):
        registry.register("   ", target)


def test_async_registry_rejects_unsupported_required_argument() -> None:
    registry = AsyncPythonTargetRegistry()

    async def target(customer_id: str) -> None:
        del customer_id

    with pytest.raises(InvalidAsyncCallableTargetError, match="must not require arguments"):
        registry.register("refresh", target)


def test_async_registry_unregister_removes_exact_target_and_capabilities() -> None:
    registry = AsyncPythonTargetRegistry()

    async def target(
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


def test_async_executor_rejects_non_async_target_kind() -> None:
    executor = _executor(AsyncPythonTargetRegistry())

    with pytest.raises(UnsupportedTargetError):
        executor.prepare(TargetRef.python("refresh"))


def test_async_executor_invokes_coroutine_successfully() -> None:
    registry = AsyncPythonTargetRegistry()
    calls: list[str] = []

    async def target() -> None:
        await asyncio.sleep(0)
        calls.append("called")

    registry.register("refresh", target)
    executor = _executor(registry)

    outcome = executor.execute(executor.prepare(TargetRef.async_python("refresh")))

    assert outcome.succeeded
    assert calls == ["called"]


def test_async_executor_normalizes_exception_without_raw_message() -> None:
    registry = AsyncPythonTargetRegistry()

    async def target() -> None:
        raise RuntimeError("database password=secret")

    registry.register("refresh", target)
    executor = _executor(registry)

    outcome = executor.execute(executor.prepare(TargetRef.async_python("refresh")))

    assert outcome.failure is not None
    assert outcome.failure.category is FailureCategory.UNKNOWN
    assert outcome.failure.code == "python_async.exception"
    assert outcome.failure.details == (("exception_type", "RuntimeError"),)
    assert "secret" not in outcome.failure.message
    assert "secret" not in repr(outcome.failure.details)


def test_async_executor_injects_fencing_and_cancellation_tokens() -> None:
    registry = AsyncPythonTargetRegistry()
    observed: list[tuple[bool, int]] = []

    async def target(
        cancellation_token: CancellationToken,
        fencing_token: int,
    ) -> None:
        observed.append((cancellation_token.is_cancelled, fencing_token))

    registry.register("fenced", target)
    controller = InMemoryCancellationController()
    token = controller.token_for("execution-1")
    executor = _executor(registry)

    outcome = executor.execute(
        executor.prepare(TargetRef.async_python("fenced")),
        cancellation_token=token,
        fencing_token=7,
    )

    assert outcome.succeeded
    assert observed == [(False, 7)]


def test_async_executor_pre_cancelled_token_never_invokes_target() -> None:
    registry = AsyncPythonTargetRegistry()
    calls: list[str] = []

    async def target() -> None:
        calls.append("called")

    registry.register("refresh", target)
    controller = InMemoryCancellationController()
    token = controller.token_for("execution-1")
    controller.cancel("execution-1")
    executor = _executor(registry)

    outcome = executor.execute(
        executor.prepare(TargetRef.async_python("refresh")),
        cancellation_token=token,
    )

    assert outcome.failure is not None
    assert outcome.failure.category is FailureCategory.CANCELLED
    assert calls == []


def test_async_executor_cooperative_cancellation_is_normalized() -> None:
    registry = AsyncPythonTargetRegistry()
    controller = InMemoryCancellationController()
    token = controller.token_for("execution-1")
    controller.cancel("execution-1")

    async def target(cancellation_token: CancellationToken) -> None:
        cancellation_token.raise_if_cancelled()

    registry.register("refresh", target)
    executor = _executor(registry)

    outcome = executor.execute(
        executor.prepare(TargetRef.async_python("refresh")),
        cancellation_token=token,
    )

    assert outcome.failure is not None
    assert outcome.failure.category is FailureCategory.CANCELLED


def test_async_executor_timeout_cancels_coroutine_and_returns_timeout() -> None:
    registry = AsyncPythonTargetRegistry()
    cancelled: list[bool] = []

    async def target() -> None:
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)

    registry.register("slow", target)
    executor = _executor(registry)

    outcome = executor.execute(
        executor.prepare(TargetRef.async_python("slow")),
        timeout=Duration.seconds(0.01),
    )

    assert outcome.failure is not None
    assert outcome.failure.category is FailureCategory.TIMEOUT
    assert cancelled == [True]


def test_async_executor_can_run_when_caller_already_has_running_event_loop() -> None:
    registry = AsyncPythonTargetRegistry()

    async def target() -> None:
        await asyncio.sleep(0)

    registry.register("refresh", target)
    executor = _executor(registry)
    prepared = executor.prepare(TargetRef.async_python("refresh"))

    async def caller() -> bool:
        return executor.execute(prepared).succeeded

    assert asyncio.run(caller())
