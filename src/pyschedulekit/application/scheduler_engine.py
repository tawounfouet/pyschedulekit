"""Application service evaluating due Schedules into durable execution intents."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.domain.execution_request import ExecutionRequest
from pyschedulekit.domain.misfire import (
    MisfireDecision,
    MisfireDecisionAction,
    MisfireEvaluator,
)
from pyschedulekit.domain.occurrence import OccurrenceKey, OccurrencePlanner
from pyschedulekit.domain.schedule import ScheduleId, ScheduleState
from pyschedulekit.domain.time import Instant
from pyschedulekit.ports.persistence import PersistenceConflictError, UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class MisfireEvaluationRecord:
    """Decision evidence for one newly evaluated due occurrence."""

    occurrence_key: OccurrenceKey
    decision: MisfireDecision


@dataclass(frozen=True, slots=True)
class SchedulerEvaluationResult:
    """Result of one deterministic SchedulerEngine evaluation cycle."""

    evaluation_now: Instant
    requests: tuple[ExecutionRequest, ...]
    conflicts: tuple[ScheduleId, ...]
    misfire_decisions: tuple[MisfireEvaluationRecord, ...] = ()
    unsupported_policy_schedules: tuple[ScheduleId, ...] = ()


class SchedulerEngine:
    """Materialize due occurrences into durable requests under explicit policies."""

    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        occurrence_planner: OccurrencePlanner | None = None,
        misfire_evaluator: MisfireEvaluator | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._occurrence_planner = occurrence_planner or OccurrencePlanner()
        self._misfire_evaluator = misfire_evaluator or MisfireEvaluator()

    def evaluate(
        self,
        *,
        evaluation_now: Instant,
        limit: int = 100,
    ) -> SchedulerEvaluationResult:
        """Evaluate due Schedules using one explicit wall-clock snapshot."""

        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        schedule_ids = self._discover_due_schedule_ids(
            evaluation_now=evaluation_now,
            limit=limit,
        )

        requests: list[ExecutionRequest] = []
        conflicts: list[ScheduleId] = []
        decisions: list[MisfireEvaluationRecord] = []
        unsupported: list[ScheduleId] = []

        for schedule_id in schedule_ids:
            try:
                request, record, policy_supported = self._evaluate_schedule(
                    schedule_id=schedule_id,
                    evaluation_now=evaluation_now,
                )
            except PersistenceConflictError:
                conflicts.append(schedule_id)
                continue

            if request is not None:
                requests.append(request)
            if record is not None:
                decisions.append(record)
            if not policy_supported:
                unsupported.append(schedule_id)

        return SchedulerEvaluationResult(
            evaluation_now=evaluation_now,
            requests=tuple(requests),
            conflicts=tuple(conflicts),
            misfire_decisions=tuple(decisions),
            unsupported_policy_schedules=tuple(unsupported),
        )

    def _discover_due_schedule_ids(
        self,
        *,
        evaluation_now: Instant,
        limit: int,
    ) -> tuple[ScheduleId, ...]:
        with self._uow_factory() as uow:
            due = uow.schedules.list_due(now=evaluation_now, limit=limit)
            return tuple(schedule.id for schedule in due)

    def _evaluate_schedule(
        self,
        *,
        schedule_id: ScheduleId,
        evaluation_now: Instant,
    ) -> tuple[ExecutionRequest | None, MisfireEvaluationRecord | None, bool]:
        with self._uow_factory() as uow:
            schedule = uow.schedules.get(schedule_id)
            if schedule is None:
                return None, None, True

            if schedule.state is not ScheduleState.ACTIVE:
                return None, None, True

            checkpoint = schedule.next_run_time
            if checkpoint is None or checkpoint > evaluation_now:
                return None, None, True

            occurrence = self._occurrence_planner.current(schedule)
            if occurrence is None:
                return None, None, True

            existing = uow.requests.get_by_occurrence(occurrence.key)
            if existing is not None:
                schedule.advance_next_run_after(reference=occurrence.scheduled_at)
                uow.schedules.save(schedule)
                uow.commit()
                return existing, None, True

            decision = self._misfire_evaluator.evaluate(
                scheduled_at=occurrence.scheduled_at,
                evaluated_at=evaluation_now,
                policy=schedule.definition.misfire,
            )
            record = MisfireEvaluationRecord(
                occurrence_key=occurrence.key,
                decision=decision,
            )

            if decision.action in (
                MisfireDecisionAction.CATCH_UP,
                MisfireDecisionAction.COALESCE,
            ):
                return None, record, False

            if decision.action is MisfireDecisionAction.SKIP:
                schedule.advance_next_run_after(reference=occurrence.scheduled_at)
                uow.schedules.save(schedule)
                uow.commit()
                return None, record, True

            request = ExecutionRequest.from_occurrence(
                occurrence=occurrence,
                target=schedule.definition.target,
                created_at=evaluation_now,
            )
            uow.requests.add(request)

            schedule.advance_next_run_after(reference=occurrence.scheduled_at)
            uow.schedules.save(schedule)
            uow.commit()

            return request, record, True
