"""Concurrency admission coordination for durable ExecutionRequests."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from pyschedulekit.application.admission_lock import ScheduleAdmissionLockCoordinator
from pyschedulekit.application.execution_service import (
    ExecutionConsistencyError,
    ExecutionRequestNotFoundError,
)
from pyschedulekit.domain.concurrency import (
    ConcurrencyDecision,
    ConcurrencyDecisionAction,
    ConcurrencyEvaluator,
)
from pyschedulekit.domain.execution import Execution
from pyschedulekit.domain.execution_request import (
    ExecutionRequestState,
    InvalidExecutionRequestTransitionError,
    RequestId,
)
from pyschedulekit.domain.time import Instant
from pyschedulekit.ports.persistence import UnitOfWorkFactory

_PROCESS_ADMISSION_LOCK = RLock()


@dataclass(frozen=True, slots=True)
class AdmissionResult:
    """Result of one serialized admission attempt."""

    request_id: RequestId
    action: ConcurrencyDecisionAction
    decision: ConcurrencyDecision | None
    execution: Execution | None
    reused: bool = False
    lock_denied: bool = False


class ConcurrencyCoordinator:
    """Coordinate count-and-admit with optional durable Schedule ownership."""

    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        evaluator: ConcurrencyEvaluator | None = None,
        admission_lock_coordinator: ScheduleAdmissionLockCoordinator | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._evaluator = evaluator or ConcurrencyEvaluator()
        self._admission_lock_coordinator = admission_lock_coordinator
        self._lock = _PROCESS_ADMISSION_LOCK

    def admit(
        self,
        *,
        request_id: RequestId,
        created_at: Instant,
    ) -> AdmissionResult:
        """Atomically decide and persist one admission."""

        if self._admission_lock_coordinator is None:
            with self._lock:
                return self._admit_locked(
                    request_id=request_id,
                    created_at=created_at,
                )

        schedule_id = self._schedule_id_for_request(request_id)
        acquisition = self._admission_lock_coordinator.acquire(
            schedule_id=schedule_id,
            now=created_at,
        )
        if not acquisition.acquired or acquisition.handle is None:
            return AdmissionResult(
                request_id=request_id,
                action=ConcurrencyDecisionAction.QUEUE,
                decision=None,
                execution=None,
                reused=False,
                lock_denied=True,
            )

        try:
            return self._admit_locked(
                request_id=request_id,
                created_at=created_at,
            )
        finally:
            self._admission_lock_coordinator.release(
                handle=acquisition.handle,
                released_at=created_at,
            )

    def _schedule_id_for_request(self, request_id: RequestId):
        with self._uow_factory() as uow:
            request = uow.requests.get(request_id)
            if request is None:
                raise ExecutionRequestNotFoundError(request_id.value)
            return request.occurrence_key.schedule_id

    def _admit_locked(
        self,
        *,
        request_id: RequestId,
        created_at: Instant,
    ) -> AdmissionResult:
        with self._uow_factory() as uow:
            request = uow.requests.get(request_id)
            if request is None:
                raise ExecutionRequestNotFoundError(request_id.value)

            existing = uow.executions.get_by_request(request.id)

            if request.state is ExecutionRequestState.DISPATCHED:
                if existing is None:
                    raise ExecutionConsistencyError(
                        "Dispatched ExecutionRequest has no persisted Execution."
                    )
                return AdmissionResult(
                    request_id=request.id,
                    action=ConcurrencyDecisionAction.ADMIT,
                    decision=None,
                    execution=existing,
                    reused=True,
                )

            if request.state is ExecutionRequestState.DROPPED:
                return AdmissionResult(
                    request_id=request.id,
                    action=ConcurrencyDecisionAction.DROP,
                    decision=None,
                    execution=None,
                    reused=True,
                )

            if request.state is ExecutionRequestState.CANCELLED:
                raise InvalidExecutionRequestTransitionError(
                    "Cancelled ExecutionRequest cannot be admitted."
                )

            if existing is not None:
                request.mark_dispatched()
                uow.requests.save(request)
                uow.commit()
                return AdmissionResult(
                    request_id=request.id,
                    action=ConcurrencyDecisionAction.ADMIT,
                    decision=None,
                    execution=existing,
                    reused=True,
                )

            active_instances = uow.executions.count_non_terminal_for_schedule(
                request.occurrence_key.schedule_id
            )
            decision = self._evaluator.evaluate(
                policy=request.concurrency_policy,
                active_instances=active_instances,
            )

            if decision.action is ConcurrencyDecisionAction.QUEUE:
                request.wait_for_admission()
                uow.requests.save(request)
                uow.commit()
                return AdmissionResult(
                    request_id=request.id,
                    action=decision.action,
                    decision=decision,
                    execution=None,
                )

            if decision.action is ConcurrencyDecisionAction.DROP:
                request.drop()
                uow.requests.save(request)
                uow.commit()
                return AdmissionResult(
                    request_id=request.id,
                    action=decision.action,
                    decision=decision,
                    execution=None,
                )

            request.mark_dispatched()
            execution = Execution.from_request(
                request=request,
                created_at=created_at,
            )
            uow.requests.save(request)
            uow.executions.add(execution)
            uow.commit()

            return AdmissionResult(
                request_id=request.id,
                action=decision.action,
                decision=decision,
                execution=execution,
            )
