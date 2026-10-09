"""CAL-02 integration qualification for SchedulerEngine calendar semantics."""

from datetime import UTC, datetime

from pyschedulekit.application.scheduler_engine import SchedulerEngine
from pyschedulekit.domain.calendar import BusinessCalendar, CalendarRef, CalendarRevision
from pyschedulekit.domain.misfire import MisfirePolicy
from pyschedulekit.domain.schedule import (
    PersistenceVersion,
    Schedule,
    ScheduleDefinition,
    ScheduleId,
    ScheduleRevision,
    ScheduleState,
    TargetRef,
)
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.domain.triggers import IntervalTrigger
from pyschedulekit.infrastructure.calendar import InMemoryCalendarProvider
from pyschedulekit.infrastructure.memory import InMemoryUnitOfWorkFactory


def _instant(day: int, hour: int = 10) -> Instant:
    return Instant(datetime(2026, 1, day, hour, tzinfo=UTC))


def _calendar() -> BusinessCalendar:
    return BusinessCalendar(
        calendar_ref=CalendarRef("business-days"),
        revision=CalendarRevision(1),
    )


def _daily_definition(
    calendar: BusinessCalendar,
    *,
    misfire: MisfirePolicy | None = None,
) -> ScheduleDefinition:
    return ScheduleDefinition(
        target=TargetRef.python("jobs:calendar"),
        trigger=IntervalTrigger(
            every=Duration.days(1),
            anchor=_instant(2),
        ),
        calendar=calendar.snapshot_ref,
        misfire=misfire if misfire is not None else MisfirePolicy.run_now(),
    )


def _persist(factory: InMemoryUnitOfWorkFactory, schedule: Schedule) -> None:
    with factory() as uow:
        uow.schedules.add(schedule)
        uow.commit()


def _load(factory: InMemoryUnitOfWorkFactory, schedule_id: str) -> Schedule:
    with factory() as uow:
        schedule = uow.schedules.get(ScheduleId(schedule_id))
        assert schedule is not None
        return schedule


def test_engine_materializes_friday_then_advances_checkpoint_to_monday() -> None:
    calendar = _calendar()
    provider = InMemoryCalendarProvider([calendar])
    factory = InMemoryUnitOfWorkFactory()
    schedule = Schedule.create(
        schedule_id=ScheduleId("weekday"),
        definition=_daily_definition(calendar),
        reference=_instant(2, hour=9),
        calendar=calendar,
    )
    _persist(factory, schedule)

    result = SchedulerEngine(
        uow_factory=factory,
        calendar_provider=provider,
    ).evaluate(evaluation_now=_instant(2))

    assert [request.occurrence_key.scheduled_at for request in result.requests] == [_instant(2)]
    assert _load(factory, "weekday").next_run_time == _instant(5)


def test_calendar_aware_catch_up_never_materializes_weekend_candidates() -> None:
    calendar = _calendar()
    provider = InMemoryCalendarProvider([calendar])
    factory = InMemoryUnitOfWorkFactory()
    schedule = Schedule.create(
        schedule_id=ScheduleId("catch-up"),
        definition=_daily_definition(
            calendar,
            misfire=MisfirePolicy.catch_up(max_occurrences=10),
        ),
        reference=_instant(2, hour=9),
        calendar=calendar,
    )
    _persist(factory, schedule)

    result = SchedulerEngine(
        uow_factory=factory,
        calendar_provider=provider,
    ).evaluate(evaluation_now=_instant(6))

    assert [request.occurrence_key.scheduled_at for request in result.requests] == [
        _instant(2),
        _instant(5),
        _instant(6),
    ]
    assert [key.scheduled_at for key in result.recovery_records[0].considered_occurrence_keys] == [
        _instant(2),
        _instant(5),
        _instant(6),
    ]
    assert _load(factory, "catch-up").next_run_time == _instant(7)


def test_engine_self_heals_legacy_raw_calendar_checkpoint_without_materializing_it() -> None:
    calendar = _calendar()
    provider = InMemoryCalendarProvider([calendar])
    factory = InMemoryUnitOfWorkFactory()
    schedule = Schedule(
        schedule_id=ScheduleId("legacy-checkpoint"),
        definition=_daily_definition(calendar),
        state=ScheduleState.ACTIVE,
        revision=ScheduleRevision(1),
        persistence_version=PersistenceVersion(0),
        next_run_time=_instant(3),
    )
    _persist(factory, schedule)

    result = SchedulerEngine(
        uow_factory=factory,
        calendar_provider=provider,
    ).evaluate(evaluation_now=_instant(3))

    assert result.requests == ()
    healed = _load(factory, "legacy-checkpoint")
    assert healed.next_run_time == _instant(5)
    assert healed.persistence_version == PersistenceVersion(1)
