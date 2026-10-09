"""Deterministic POST-06 chaos/fault-injection campaign.

The scenarios inject known failures at explicit seams. There is no randomness and no
external service dependency: a failure should be exactly reproducible from the same source
revision.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from pyschedulekit import (
    Duration,
    FixedBackoff,
    Instant,
    IntervalTrigger,
    OutboxMessage,
    RetryPolicy,
    Scheduler,
    SqliteUnitOfWorkFactory,
    TargetRef,
)
from pyschedulekit.application.admission_lock import ScheduleAdmissionLockCoordinator
from pyschedulekit.application.claims import ExecutionClaimCoordinator
from pyschedulekit.application.concurrency import AdmissionResult, ConcurrencyCoordinator
from pyschedulekit.application.execution_service import ExecutionService
from pyschedulekit.application.observability import Observer
from pyschedulekit.application.recovery import CrashRecoveryService
from pyschedulekit.application.run_pending import RunPendingResult
from pyschedulekit.application.runtime import ContinuousSchedulerLoop
from pyschedulekit.domain.admission_lock import (
    ScheduleAdmissionLockHandle,
    ScheduleAdmissionLockState,
)
from pyschedulekit.domain.claim import ClaimOwnershipError, ExecutionClaimState, WorkerId
from pyschedulekit.domain.execution import ExecutionState
from pyschedulekit.domain.execution_request import ExecutionRequest, RequestId
from pyschedulekit.domain.occurrence import Occurrence, OccurrenceKey
from pyschedulekit.domain.retry import RetryPolicy as DomainRetryPolicy
from pyschedulekit.domain.schedule import (
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleRevision,
)
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory
from pyschedulekit.infrastructure.observability import InMemoryObservationSink
from pyschedulekit.infrastructure.sqlite import SqliteUnitOfWorkFactory as InternalSqliteFactory
from pyschedulekit.ports.persistence import PersistenceConflictError
from pyschedulekit.testing import FixedClock, MutableClock


@dataclass(frozen=True, slots=True)
class ChaosScenarioResult:
    name: str
    invariant: str
    passed: bool
    evidence: dict[str, object]
    error: str | None = None


def _instant(
    *,
    hour: int = 10,
    minute: int = 0,
    second: int = 0,
) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, minute, second, tzinfo=UTC))


def _retry_after_executor_failure() -> dict[str, object]:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    attempts = 0

    def flaky_target() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("injected executor failure")

    scheduler.add_schedule(
        id="chaos-retry",
        target=flaky_target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(minute=10),
        ),
        retry=RetryPolicy(
            max_attempts=3,
            backoff=FixedBackoff(Duration.minutes(2)),
        ),
    )

    clock.advance(Duration.minutes(10))
    failed = scheduler.run_pending()
    assert failed.retry_scheduled == 1
    assert failed.failed == 0
    assert attempts == 1

    premature = scheduler.run_pending()
    assert premature.executions == ()
    assert attempts == 1

    clock.advance(Duration.minutes(2))
    recovered = scheduler.run_pending()
    assert recovered.succeeded == 1
    assert recovered.failed == 0
    assert attempts == 2
    assert recovered.executions[0].execution.state is ExecutionState.SUCCESS

    return {
        "attempts": attempts,
        "retry_scheduled_after_fault": failed.retry_scheduled,
        "premature_execution_count": len(premature.executions),
        "final_state": recovered.executions[0].execution.state.value,
    }


class _FailOncePublisher:
    def __init__(self) -> None:
        self.calls = 0
        self.published: list[str] = []

    def publish(self, message: OutboxMessage) -> None:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("injected broker outage")
        self.published.append(message.id.value)


def _outbox_recovers_after_broker_failure() -> dict[str, object]:
    with TemporaryDirectory() as directory:
        database = Path(directory) / "chaos-outbox.db"
        factory = SqliteUnitOfWorkFactory(database)
        clock = MutableClock(_instant())
        scheduler = Scheduler(clock=clock, uow_factory=factory)

        scheduler.add_schedule(
            id="chaos-outbox",
            target=lambda: None,
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(minute=10),
            ),
        )
        clock.advance(Duration.minutes(10))
        cycle = scheduler.run_pending()
        assert cycle.succeeded == 1

        publisher = _FailOncePublisher()
        first = scheduler.dispatch_outbox(publisher)
        assert first.failed == 1
        assert first.published == 1

        with factory() as uow:
            after_fault = uow.outbox.list_pending(limit=10)
        assert len(after_fault) == 1

        second = scheduler.dispatch_outbox(publisher)
        assert second.failed == 0
        assert second.published == 1

        with factory() as uow:
            after_recovery = uow.outbox.list_pending(limit=10)
        assert after_recovery == []

        return {
            "first_dispatch_failed": first.failed,
            "first_dispatch_published": first.published,
            "pending_after_fault": len(after_fault),
            "second_dispatch_published": second.published,
            "pending_after_recovery": len(after_recovery),
            "publisher_calls": publisher.calls,
        }


def _empty_cycle_result() -> RunPendingResult:
    return RunPendingResult(
        evaluation_now=_instant(),
        materialized_request_ids=(),
        executions=(),
        schedule_conflicts=(),
        unsupported_policy_schedules=(),
        recovery_limit_schedules=(),
        admissions=(),
        errors=(),
    )


class _FailOnceRunPendingService:
    def __init__(self) -> None:
        self.calls = 0

    def run_pending(self, *, limit: int = 100) -> RunPendingResult:
        del limit
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("injected runtime cycle failure")
        return _empty_cycle_result()


class _FixedWakeUpPlanner:
    def next_delay(self, *, max_sleep: Duration) -> Duration:
        return max_sleep


class _StopAfterTwoWaits:
    def __init__(self) -> None:
        self.calls = 0
        self.runtime: ContinuousSchedulerLoop | None = None

    def wait(self, *, duration: Duration, wake_event: Event) -> bool:
        del duration
        self.calls += 1
        if self.calls == 2:
            assert self.runtime is not None
            self.runtime.request_stop()
            return True
        return wake_event.is_set()


def _runtime_survives_cycle_failure() -> dict[str, object]:
    sink = InMemoryObservationSink()
    service = _FailOnceRunPendingService()
    waiter = _StopAfterTwoWaits()
    runtime = ContinuousSchedulerLoop(
        run_pending_service=service,
        waiter=waiter,
        wakeup_planner=_FixedWakeUpPlanner(),
        clock=FixedClock(_instant()),
        observer=Observer(sink),
    )
    waiter.runtime = runtime

    runtime.run_forever(
        max_sleep=Duration.seconds(1),
        limit=5,
    )

    errors = sink.by_name("runtime.cycle.error")
    assert service.calls == 2
    assert runtime.cycles_completed == 1
    assert runtime.last_result == _empty_cycle_result()
    assert not runtime.is_running
    assert len(errors) == 1

    return {
        "service_calls": service.calls,
        "successful_cycles": runtime.cycles_completed,
        "observed_cycle_errors": len(errors),
        "runtime_running_after_stop": runtime.is_running,
    }


class _ConflictAfterLockCoordinator(ConcurrencyCoordinator):
    def _admit_locked(
        self,
        *,
        request_id: RequestId,
        created_at: Instant,
        lock_handle: ScheduleAdmissionLockHandle | None,
    ) -> AdmissionResult:
        del request_id, created_at, lock_handle
        raise PersistenceConflictError("injected admission persistence conflict")


def _admission_lock_recovers_after_conflict() -> dict[str, object]:
    factory = InMemoryUnitOfWorkFactory()
    schedule_id = ScheduleId("chaos-admission")
    schedule = Schedule.create(
        schedule_id=schedule_id,
        definition=ScheduleDefinition(
            target=TargetRef.python("chaos:admission"),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(),
            ),
        ),
        reference=_instant(),
    )
    request = ExecutionRequest(
        id=RequestId("chaos-admission-request"),
        occurrence_key=OccurrenceKey(
            schedule_id=schedule_id,
            schedule_revision=ScheduleRevision(1),
            scheduled_at=_instant(),
        ),
        target=schedule.definition.target,
        created_at=_instant(),
    )

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.commit()

    owner = ScheduleAdmissionLockCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("chaos-owner"),
        ttl=Duration.seconds(5),
    )
    coordinator = _ConflictAfterLockCoordinator(
        uow_factory=factory,
        admission_lock_coordinator=owner,
    )

    denied = coordinator.admit(
        request_id=request.id,
        created_at=_instant(),
    )
    assert denied.lock_denied

    with factory() as uow:
        released = uow.admission_locks.get(schedule_id)
    assert released is not None
    assert released.state is ScheduleAdmissionLockState.RELEASED

    contender = ScheduleAdmissionLockCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("chaos-contender"),
        ttl=Duration.seconds(5),
    )
    reacquired = contender.acquire(
        schedule_id=schedule_id,
        now=_instant(),
    )
    assert reacquired.acquired
    assert reacquired.handle is not None

    return {
        "conflict_reported_as_lock_denied": denied.lock_denied,
        "lock_state_after_conflict": released.state.value,
        "contender_reacquired": reacquired.acquired,
        "new_owner": reacquired.handle.worker_id.value,
    }


def _seed_running_execution(
    factory: InternalSqliteFactory,
) -> tuple[ExecutionService, object, object, object]:
    schedule = Schedule.create(
        schedule_id=ScheduleId("chaos-fencing"),
        definition=ScheduleDefinition(
            target=TargetRef.python("chaos:fencing"),
            trigger=IntervalTrigger(
                every=Duration.hours(1),
                anchor=_instant(hour=11),
            ),
            retry=DomainRetryPolicy.none(),
        ),
        reference=_instant(hour=9),
    )
    occurrence = Occurrence(
        schedule_id=schedule.id,
        schedule_revision=ScheduleRevision(1),
        scheduled_at=_instant(),
    )
    request = ExecutionRequest.from_occurrence(
        occurrence=occurrence,
        target=schedule.definition.target,
        created_at=_instant(),
        retry_policy=DomainRetryPolicy.none(),
    )

    with factory() as uow:
        uow.schedules.add(schedule)
        uow.requests.add(request)
        uow.commit()

    service = ExecutionService(uow_factory=factory)
    execution = service.dispatch(
        request_id=request.id,
        created_at=_instant(),
    )
    owner = ExecutionClaimCoordinator(
        uow_factory=factory,
        worker_id=WorkerId("chaos-worker-a"),
        ttl=Duration.seconds(30),
    )
    acquired = owner.acquire(
        execution_id=execution.id,
        now=_instant(),
    )
    assert acquired.handle is not None
    attempt = service.start_attempt(
        execution_id=execution.id,
        started_at=_instant(),
        claim_handle=acquired.handle,
    )
    return service, execution, attempt, acquired.handle


def _stale_owner_is_fenced_after_recovery() -> dict[str, object]:
    with TemporaryDirectory() as directory:
        factory = InternalSqliteFactory(Path(directory) / "chaos-fencing.db")
        service, execution, attempt, stale_handle = _seed_running_execution(factory)

        recovery = CrashRecoveryService(
            clock=MutableClock(_instant(second=30)),
            uow_factory=factory,
            claim_coordinator=ExecutionClaimCoordinator(
                uow_factory=factory,
                worker_id=WorkerId("chaos-worker-b"),
                ttl=Duration.seconds(30),
            ),
        )
        recovered = recovery.recover()
        assert recovered.failed_execution_ids == (execution.id,)

        stale_completion_blocked = False
        try:
            service.succeed_attempt(
                attempt_id=attempt.id,
                completed_at=_instant(second=31),
                claim_handle=stale_handle,
            )
        except ClaimOwnershipError:
            stale_completion_blocked = True

        assert stale_completion_blocked

        with factory() as uow:
            persisted = uow.executions.get(execution.id)
            claim = uow.claims.get(execution.id)

        assert persisted is not None
        assert claim is not None
        assert persisted.state is ExecutionState.FAILED
        assert claim.state is ExecutionClaimState.RELEASED
        assert claim.generation == stale_handle.generation + 1

        return {
            "recovered_execution_count": len(recovered.failed_execution_ids),
            "stale_completion_blocked": stale_completion_blocked,
            "final_execution_state": persisted.state.value,
            "final_claim_state": claim.state.value,
            "fencing_generation": claim.generation,
        }


SCENARIOS = (
    (
        "executor_retry_recovery",
        "A transient execution fault is retried only after backoff and can recover.",
        _retry_after_executor_failure,
    ),
    (
        "outbox_broker_recovery",
        "A failed outbox publish remains pending and can be published later.",
        _outbox_recovers_after_broker_failure,
    ),
    (
        "runtime_cycle_supervision",
        "One cycle exception is observed without permanently terminating the runtime.",
        _runtime_survives_cycle_failure,
    ),
    (
        "admission_conflict_compensation",
        "A persistence conflict cannot strand the admission lock.",
        _admission_lock_recovers_after_conflict,
    ),
    (
        "stale_owner_fencing",
        "An expired owner cannot commit after recovery advances the fencing generation.",
        _stale_owner_is_fenced_after_recovery,
    ),
)


def run_campaign() -> dict[str, object]:
    results: list[ChaosScenarioResult] = []

    for name, invariant, scenario in SCENARIOS:
        try:
            evidence = scenario()
        except Exception as exc:
            results.append(
                ChaosScenarioResult(
                    name=name,
                    invariant=invariant,
                    passed=False,
                    evidence={},
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
        else:
            results.append(
                ChaosScenarioResult(
                    name=name,
                    invariant=invariant,
                    passed=True,
                    evidence=evidence,
                )
            )

    return {
        "schema_version": 1,
        "deterministic": True,
        "scenario_count": len(results),
        "passed": sum(result.passed for result in results),
        "failed": sum(not result.passed for result in results),
        "scenarios": [asdict(result) for result in results],
    }


def assert_campaign_passed(report: dict[str, object]) -> None:
    failed = int(report["failed"])
    if failed:
        scenarios = report["scenarios"]
        assert isinstance(scenarios, list)
        failures = [
            f"{scenario['name']}: {scenario['error']}"
            for scenario in scenarios
            if isinstance(scenario, dict) and not scenario["passed"]
        ]
        raise AssertionError("Chaos campaign failed:\n" + "\n".join(failures))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run_campaign()
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)

    if args.output is not None:
        args.output.write_text(rendered + "\n", encoding="utf-8")

    assert_campaign_passed(report)


if __name__ == "__main__":
    main()
