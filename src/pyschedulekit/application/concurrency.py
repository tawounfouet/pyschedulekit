"""Concurrency admission coordination for durable ExecutionRequests."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

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


class ConcurrencyCoordinator:
    """Serialize count-and-admit decisions inside one process."""

    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        evaluator: ConcurrencyEvaluator | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._evaluator = evaluator or ConcurrencyEvaluator()
        self._lock = _PROCESS_ADMISSION_LOCK

    def admit(
        self,
        *,
        request_id: RequestId,
        created_at: Instant,
    ) -> AdmissionResult:
        """Atomically decide and persist admission within this process."""

        with self._lock, self._uow_factory() as uow:
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
