"""Application service evaluating due Schedules into durable execution intents."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.domain.execution_request import ExecutionRequest
from pyschedulekit.domain.misfire import (
    MisfireDecision,
    MisfireDecisionAction,
    MisfireEvaluator,
    MisfirePolicyAction,
)
from pyschedulekit.domain.occurrence import Occurrence, OccurrenceKey, OccurrencePlanner
from pyschedulekit.domain.schedule import Schedule, ScheduleId, ScheduleState
from pyschedulekit.domain.time import Instant
from pyschedulekit.ports.persistence import PersistenceConflictError, UnitOfWork, UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class MisfireEvaluationRecord:
    """Decision evidence for one newly evaluated due occurrence."""

    occurrence_key: OccurrenceKey
    decision: MisfireDecision


@dataclass(frozen=True, slots=True)
class RecoveryEvaluationRecord:
    """Evidence produced while reconstructing a missed-occurrence backlog."""

    schedule_id: ScheduleId
    action: MisfirePolicyAction
    considered_occurrence_keys: tuple[OccurrenceKey, ...]
    materialized_occurrence_keys: tuple[OccurrenceKey, ...]
    has_more: bool


@dataclass(frozen=True, slots=True)
class SchedulerEvaluationResult:
    """Result of one deterministic SchedulerEngine evaluation cycle."""

    evaluation_now: Instant
    requests: tuple[ExecutionRequest, ...]
    conflicts: tuple[ScheduleId, ...]
    misfire_decisions: tuple[MisfireEvaluationRecord, ...] = ()
    unsupported_policy_schedules: tuple[ScheduleId, ...] = ()
    recovery_records: tuple[RecoveryEvaluationRecord, ...] = ()
    recovery_limit_schedules: tuple[ScheduleId, ...] = ()


@dataclass(frozen=True, slots=True)
class _ScheduleEvaluation:
    requests: tuple[ExecutionRequest, ...] = ()
    misfire_record: MisfireEvaluationRecord | None = None
    recovery_record: RecoveryEvaluationRecord | None = None
    recovery_limit_exceeded: bool = False


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
        recovery_records: list[RecoveryEvaluationRecord] = []
        recovery_limit_schedules: list[ScheduleId] = []

        for schedule_id in schedule_ids:
            try:
                evaluation = self._evaluate_schedule(
                    schedule_id=schedule_id,
                    evaluation_now=evaluation_now,
                )
            except PersistenceConflictError:
                conflicts.append(schedule_id)
                continue

            requests.extend(evaluation.requests)
            if evaluation.misfire_record is not None:
                decisions.append(evaluation.misfire_record)
            if evaluation.recovery_record is not None:
                recovery_records.append(evaluation.recovery_record)
            if evaluation.recovery_limit_exceeded:
                recovery_limit_schedules.append(schedule_id)

        return SchedulerEvaluationResult(
            evaluation_now=evaluation_now,
            requests=tuple(requests),
            conflicts=tuple(conflicts),
            misfire_decisions=tuple(decisions),
            unsupported_policy_schedules=(),
            recovery_records=tuple(recovery_records),
            recovery_limit_schedules=tuple(recovery_limit_schedules),
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
    ) -> _ScheduleEvaluation:
        with self._uow_factory() as uow:
            schedule = uow.schedules.get(schedule_id)
            if schedule is None or schedule.state is not ScheduleState.ACTIVE:
                return _ScheduleEvaluation()

            checkpoint = schedule.next_run_time
            if checkpoint is None or checkpoint > evaluation_now:
                return _ScheduleEvaluation()

            occurrence = self._occurrence_planner.current(schedule)
            if occurrence is None:
                return _ScheduleEvaluation()

            configured_action = schedule.definition.misfire.action
            if configured_action not in (
                MisfirePolicyAction.CATCH_UP,
                MisfirePolicyAction.COALESCE,
            ):
                existing = uow.requests.get_by_occurrence(occurrence.key)
                if existing is not None:
                    self._advance_schedule(schedule, occurrences=(occurrence,))
                    uow.schedules.save(schedule)
                    uow.commit()
                    return _ScheduleEvaluation(requests=(existing,))

            decision = self._misfire_evaluator.evaluate(
                scheduled_at=occurrence.scheduled_at,
                evaluated_at=evaluation_now,
                policy=schedule.definition.misfire,
            )
            record = MisfireEvaluationRecord(
                occurrence_key=occurrence.key,
                decision=decision,
            )

            if decision.action is MisfireDecisionAction.CATCH_UP:
                return self._catch_up(
                    uow=uow,
                    schedule=schedule,
                    evaluation_now=evaluation_now,
                    misfire_record=record,
                )

            if decision.action is MisfireDecisionAction.COALESCE:
                return self._coalesce(
                    uow=uow,
                    schedule=schedule,
                    evaluation_now=evaluation_now,
                    misfire_record=record,
                )

            if decision.action is MisfireDecisionAction.SKIP:
                self._advance_schedule(schedule, occurrences=(occurrence,))
                uow.schedules.save(schedule)
                uow.commit()
                return _ScheduleEvaluation(misfire_record=record)

            request = self._materialize_or_reuse(
                uow=uow,
                schedule=schedule,
                occurrence=occurrence,
                created_at=evaluation_now,
            )
            self._advance_schedule(schedule, occurrences=(occurrence,))
            uow.schedules.save(schedule)
            uow.commit()

            return _ScheduleEvaluation(
                requests=(request,),
                misfire_record=record,
            )

    def _catch_up(
        self,
        *,
        uow: UnitOfWork,
        schedule: Schedule,
        evaluation_now: Instant,
        misfire_record: MisfireEvaluationRecord,
    ) -> _ScheduleEvaluation:
        backlog = self._occurrence_planner.due_backlog(
            schedule,
            until=evaluation_now,
            limit=schedule.definition.misfire.max_occurrences,
        )

        requests = tuple(
            self._materialize_or_reuse(
                uow=uow,
                schedule=schedule,
                occurrence=occurrence,
                created_at=evaluation_now,
            )
            for occurrence in backlog.occurrences
        )

        self._advance_schedule(schedule, occurrences=backlog.occurrences)
        uow.schedules.save(schedule)
        uow.commit()

        recovery_record = RecoveryEvaluationRecord(
            schedule_id=schedule.id,
            action=MisfirePolicyAction.CATCH_UP,
            considered_occurrence_keys=tuple(occurrence.key for occurrence in backlog.occurrences),
            materialized_occurrence_keys=tuple(request.occurrence_key for request in requests),
            has_more=backlog.has_more,
        )
        return _ScheduleEvaluation(
            requests=requests,
            misfire_record=misfire_record,
            recovery_record=recovery_record,
        )

    def _coalesce(
        self,
        *,
        uow: UnitOfWork,
        schedule: Schedule,
        evaluation_now: Instant,
        misfire_record: MisfireEvaluationRecord,
    ) -> _ScheduleEvaluation:
        backlog = self._occurrence_planner.due_backlog(
            schedule,
            until=evaluation_now,
            limit=schedule.definition.misfire.max_occurrences,
        )

        recovery_record = RecoveryEvaluationRecord(
            schedule_id=schedule.id,
            action=MisfirePolicyAction.COALESCE,
            considered_occurrence_keys=tuple(occurrence.key for occurrence in backlog.occurrences),
            materialized_occurrence_keys=(),
            has_more=backlog.has_more,
        )

        if backlog.has_more:
            return _ScheduleEvaluation(
                misfire_record=misfire_record,
                recovery_record=recovery_record,
                recovery_limit_exceeded=True,
            )

        existing_requests: list[ExecutionRequest] = []
        for occurrence in backlog.occurrences:
            existing = uow.requests.get_by_occurrence(occurrence.key)
            if existing is not None:
                existing_requests.append(existing)

        latest = backlog.occurrences[-1]
        latest_request = uow.requests.get_by_occurrence(latest.key)
        if latest_request is None:
            latest_request = self._materialize_or_reuse(
                uow=uow,
                schedule=schedule,
                occurrence=latest,
                created_at=evaluation_now,
            )
            existing_requests.append(latest_request)

        requests = tuple(
            sorted(
                {request.id: request for request in existing_requests}.values(),
                key=lambda request: request.occurrence_key.scheduled_at.value,
            )
        )

        self._advance_schedule(schedule, occurrences=backlog.occurrences)
        uow.schedules.save(schedule)
        uow.commit()

        completed_record = RecoveryEvaluationRecord(
            schedule_id=schedule.id,
            action=MisfirePolicyAction.COALESCE,
            considered_occurrence_keys=recovery_record.considered_occurrence_keys,
            materialized_occurrence_keys=tuple(request.occurrence_key for request in requests),
            has_more=False,
        )
        return _ScheduleEvaluation(
            requests=requests,
            misfire_record=misfire_record,
            recovery_record=completed_record,
        )

    @staticmethod
    def _materialize_or_reuse(
        *,
        uow: UnitOfWork,
        schedule: Schedule,
        occurrence: Occurrence,
        created_at: Instant,
    ) -> ExecutionRequest:
        existing = uow.requests.get_by_occurrence(occurrence.key)
        if existing is not None:
            return existing

        request = ExecutionRequest.from_occurrence(
            occurrence=occurrence,
            target=schedule.definition.target,
            created_at=created_at,
        )
        uow.requests.add(request)
        return request

    @staticmethod
    def _advance_schedule(
        schedule: Schedule,
        *,
        occurrences: tuple[Occurrence, ...],
    ) -> None:
        for occurrence in occurrences:
            schedule.advance_next_run_after(reference=occurrence.scheduled_at)
