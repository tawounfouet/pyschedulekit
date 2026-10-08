"""Testing helpers for persistence graphs."""

from __future__ import annotations

from pyschedulekit.domain.execution_request import ExecutionRequest
from pyschedulekit.domain.schedule import (
    PersistenceVersion,
    Schedule,
    ScheduleDefinition,
    ScheduleState,
)
from pyschedulekit.domain.triggers import DateTrigger
from pyschedulekit.ports.persistence import UnitOfWork


def add_request_with_parent(
    *,
    uow: UnitOfWork,
    request: ExecutionRequest,
) -> None:
    """Stage a request with an inert Schedule parent when one is missing."""

    schedule_id = request.occurrence_key.schedule_id
    if uow.schedules.get(schedule_id) is None:
        uow.schedules.add(
            Schedule(
                schedule_id=schedule_id,
                definition=ScheduleDefinition(
                    target=request.target,
                    trigger=DateTrigger(at=request.occurrence_key.scheduled_at),
                ),
                state=ScheduleState.CANCELLED,
                revision=request.occurrence_key.schedule_revision,
                persistence_version=PersistenceVersion(0),
                next_run_time=None,
            )
        )
    uow.requests.add(request)
