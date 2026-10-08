"""Immutable public result models for Scheduler operations."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.application.concurrency import AdmissionResult
from pyschedulekit.application.execution_runner import ExecutionRunResult
from pyschedulekit.application.operations import ExecutionSnapshot
from pyschedulekit.application.run_pending import (
    RunPendingError,
    RunPendingResult as InternalRunPendingResult,
)
from pyschedulekit.domain.concurrency import ConcurrencyDecision, ConcurrencyDecisionAction
from pyschedulekit.domain.execution import AttemptId, ExecutionId
from pyschedulekit.domain.execution_request import RequestId
from pyschedulekit.domain.retry import RetryDecision
from pyschedulekit.domain.schedule import ScheduleId
from pyschedulekit.domain.time import Instant
from pyschedulekit.ports.executor import ExecutorOutcome


@dataclass(frozen=True, slots=True)
class AdmissionSnapshot:
    """Immutable public view of one concurrency admission decision."""

    request_id: RequestId
    action: ConcurrencyDecisionAction
    decision: ConcurrencyDecision | None
    execution_id: ExecutionId | None
    reused: bool
    lock_denied: bool

    @classmethod
    def from_internal(cls, result: AdmissionResult) -> AdmissionSnapshot:
        return cls(
            request_id=result.request_id,
            action=result.action,
            decision=result.decision,
            execution_id=result.execution.id if result.execution is not None else None,
            reused=result.reused,
            lock_denied=result.lock_denied,
        )


@dataclass(frozen=True, slots=True)
class ExecutionRunSnapshot:
    """Immutable public view of one completed execution attempt."""

    execution: ExecutionSnapshot
    attempt_id: AttemptId
    outcome: ExecutorOutcome
    retry_decision: RetryDecision | None

    @classmethod
    def from_internal(cls, result: ExecutionRunResult) -> ExecutionRunSnapshot:
        return cls(
            execution=ExecutionSnapshot.from_execution(result.execution),
            attempt_id=result.attempt_id,
            outcome=result.outcome,
            retry_decision=result.retry_decision,
        )


@dataclass(frozen=True, slots=True)
class RunPendingResult:
    """Stable immutable result of one public Scheduler.run_pending() cycle."""

    evaluation_now: Instant
    materialized_request_ids: tuple[RequestId, ...]
    executions: tuple[ExecutionRunSnapshot, ...]
    schedule_conflicts: tuple[ScheduleId, ...]
    unsupported_policy_schedules: tuple[ScheduleId, ...]
    recovery_limit_schedules: tuple[ScheduleId, ...]
    admissions: tuple[AdmissionSnapshot, ...]
    errors: tuple[RunPendingError, ...]
    claim_denied_execution_ids: tuple[ExecutionId, ...]
    materialization_denied_schedule_ids: tuple[ScheduleId, ...]

    @classmethod
    def from_internal(cls, result: InternalRunPendingResult) -> RunPendingResult:
        return cls(
            evaluation_now=result.evaluation_now,
            materialized_request_ids=result.materialized_request_ids,
            executions=tuple(ExecutionRunSnapshot.from_internal(item) for item in result.executions),
            schedule_conflicts=result.schedule_conflicts,
            unsupported_policy_schedules=result.unsupported_policy_schedules,
            recovery_limit_schedules=result.recovery_limit_schedules,
            admissions=tuple(AdmissionSnapshot.from_internal(item) for item in result.admissions),
            errors=result.errors,
            claim_denied_execution_ids=result.claim_denied_execution_ids,
            materialization_denied_schedule_ids=result.materialization_denied_schedule_ids,
        )

    @property
    def succeeded(self) -> int:
        return sum(result.outcome.succeeded for result in self.executions)

    @property
    def failed(self) -> int:
        return sum(
            result.execution.is_terminal and not result.outcome.succeeded
            for result in self.executions
        )

    @property
    def retry_scheduled(self) -> int:
        return sum(not result.execution.is_terminal for result in self.executions)

    @property
    def queued_request_ids(self) -> tuple[RequestId, ...]:
        return tuple(
            admission.request_id
            for admission in self.admissions
            if admission.action is ConcurrencyDecisionAction.QUEUE and not admission.lock_denied
        )

    @property
    def admission_lock_denied_request_ids(self) -> tuple[RequestId, ...]:
        return tuple(admission.request_id for admission in self.admissions if admission.lock_denied)

    @property
    def dropped_request_ids(self) -> tuple[RequestId, ...]:
        return tuple(
            admission.request_id
            for admission in self.admissions
            if admission.action is ConcurrencyDecisionAction.DROP
        )
