"""LOT-20 unit tests for graceful shutdown coordination."""

from pyschedulekit.application.shutdown import ShutdownCoordinator
from pyschedulekit.domain.execution import ExecutionId
from pyschedulekit.domain.time import Duration


def test_t_shutdown_001_request_blocks_new_execution_entries() -> None:
    coordinator = ShutdownCoordinator()
    execution_id = ExecutionId("execution-a")

    coordinator.request()

    assert coordinator.is_requested is True
    assert coordinator.try_enter(execution_id) is False
    assert coordinator.snapshot() == ()


def test_t_shutdown_002_active_execution_drains_before_reset() -> None:
    coordinator = ShutdownCoordinator()
    execution_id = ExecutionId("execution-a")

    assert coordinator.try_enter(execution_id) is True
    coordinator.request()

    assert coordinator.wait_until_drained(timeout=Duration.seconds(0)) is False

    coordinator.leave(execution_id)

    assert coordinator.wait_until_drained(timeout=Duration.seconds(0)) is True
    coordinator.reset()
    assert coordinator.is_requested is False


def test_t_shutdown_003_snapshot_is_stable_and_sorted() -> None:
    coordinator = ShutdownCoordinator()

    assert coordinator.try_enter(ExecutionId("execution-b")) is True
    assert coordinator.try_enter(ExecutionId("execution-a")) is True

    assert coordinator.snapshot() == (
        ExecutionId("execution-a"),
        ExecutionId("execution-b"),
    )
