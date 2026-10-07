"""LOT-11 end-to-end tests for the public Scheduler facade."""

from datetime import UTC, datetime

import pytest

from pyschedulekit import (
    ConcurrencyOverflowPolicy,
    ConcurrencyPolicy,
    CronTrigger,
    Duration,
    GracePeriod,
    IntervalTrigger,
    MisfirePolicy,
    ScheduleId,
    Scheduler,
    TargetRef,
    Timezone,
)
from pyschedulekit.domain.execution import ExecutionState
from pyschedulekit.testing import MutableClock


def _instant(hour: int = 10, minute: int = 0):
    from pyschedulekit import Instant

    return Instant(datetime(2026, 1, 1, hour, minute, tzinfo=UTC))


def test_t_e2e_001_direct_callable_runs_once_when_due() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="schedule-1",
        target=lambda: calls.append("called"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )

    before_due = scheduler.run_pending()

    assert calls == []
    assert before_due.materialized_request_ids == ()
    assert before_due.executions == ()

    clock.advance(Duration.minutes(10))
    due = scheduler.run_pending()

    assert calls == ["called"]
    assert len(due.materialized_request_ids) == 1
    assert len(due.executions) == 1
    assert due.executions[0].execution.state is ExecutionState.SUCCESS
    assert due.succeeded == 1
    assert due.failed == 0
    assert due.errors == ()


def test_t_e2e_002_registered_target_ref_runs_successfully() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    target = scheduler.register_target(
        "refresh",
        lambda: calls.append("refresh"),
    )
    scheduler.add_schedule(
        id="schedule-1",
        target=target,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )
    clock.advance(Duration.minutes(10))

    result = scheduler.run_pending()

    assert calls == ["refresh"]
    assert result.succeeded == 1
    assert result.failed == 0


def test_t_e2e_003_run_pending_captures_evaluation_now_once() -> None:
    class CountingClock:
        def __init__(self) -> None:
            self.calls = 0

        def now(self):
            self.calls += 1
            return _instant(hour=10, minute=self.calls - 1)

    clock = CountingClock()
    scheduler = Scheduler(clock=clock)
    scheduler.add_schedule(
        id="schedule-1",
        target=lambda: None,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )
    calls_before_run = clock.calls

    result = scheduler.run_pending()

    assert result.evaluation_now == _instant(hour=10, minute=calls_before_run)
    assert clock.calls >= calls_before_run + 1


def test_t_e2e_004_one_overdue_occurrence_per_schedule_per_cycle() -> None:
    clock = MutableClock(_instant(hour=10))
    scheduler = Scheduler(clock=clock)
    calls: list[int] = []

    scheduler.add_schedule(
        id="schedule-1",
        target=lambda: calls.append(len(calls) + 1),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )

    clock.advance(Duration.minutes(35))

    first = scheduler.run_pending()
    second = scheduler.run_pending()

    assert calls == [1, 2]
    assert len(first.executions) == 1
    assert len(second.executions) == 1


def test_t_e2e_005_callable_exception_is_reported_as_failed_execution() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)

    def failing() -> None:
        raise RuntimeError("boom")

    scheduler.add_schedule(
        id="schedule-1",
        target=failing,
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )
    clock.advance(Duration.minutes(10))

    result = scheduler.run_pending()

    assert len(result.executions) == 1
    assert result.executions[0].execution.state is ExecutionState.FAILED
    assert result.succeeded == 0
    assert result.failed == 1
    assert result.errors == ()


def test_t_e2e_006_unresolved_target_isolated_from_other_request() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="a-missing",
        target=TargetRef.python("not-registered"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )
    scheduler.add_schedule(
        id="b-working",
        target=lambda: calls.append("working"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )

    clock.advance(Duration.minutes(10))
    result = scheduler.run_pending()

    assert calls == ["working"]
    assert len(result.materialized_request_ids) == 2
    assert len(result.executions) == 1
    assert result.executions[0].execution.state is ExecutionState.SUCCESS
    assert len(result.errors) == 1
    assert result.errors[0].code == "executor.target_resolution"


def test_t_e2e_007_limit_bounds_schedule_materialization() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    for schedule_id in ("schedule-c", "schedule-a", "schedule-b"):
        scheduler.add_schedule(
            id=schedule_id,
            target=lambda schedule_id=schedule_id: calls.append(schedule_id),
            trigger=IntervalTrigger(
                every=Duration.minutes(10),
                anchor=_instant(hour=10, minute=10),
            ),
        )

    clock.advance(Duration.minutes(10))
    result = scheduler.run_pending(limit=2)

    assert len(result.materialized_request_ids) == 2
    assert calls == ["schedule-a", "schedule-b"]


def test_t_e2e_008_no_due_work_is_a_noop() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)

    result = scheduler.run_pending()

    assert result.materialized_request_ids == ()
    assert result.executions == ()
    assert result.schedule_conflicts == ()
    assert result.errors == ()
    assert result.succeeded == 0
    assert result.failed == 0


def test_t_e2e_009_unresolved_queued_execution_can_run_after_target_registration() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="schedule-1",
        target=TargetRef.python("late-registration"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
    )
    clock.advance(Duration.minutes(10))

    first = scheduler.run_pending()

    assert first.executions == ()
    assert len(first.errors) == 1
    assert first.errors[0].code == "executor.target_resolution"

    scheduler.register_target(
        "late-registration",
        lambda: calls.append("recovered"),
    )

    second = scheduler.run_pending()

    assert calls == ["recovered"]
    assert len(second.executions) == 1
    assert second.executions[0].execution.state is ExecutionState.SUCCESS
    assert second.errors == ()


def test_t_e2e_010_cron_trigger_runs_through_public_scheduler() -> None:
    from pyschedulekit import Instant

    clock = MutableClock(Instant(datetime(2026, 1, 5, 7, 59, tzinfo=UTC)))
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="paris-morning",
        target=lambda: calls.append("cron"),
        trigger=CronTrigger(
            "0 9 * * 1-5",
            timezone=Timezone("Europe/Paris"),
        ),
    )

    before_due = scheduler.run_pending()
    assert calls == []
    assert before_due.executions == ()

    clock.advance(Duration.minutes(1))
    due = scheduler.run_pending()

    assert calls == ["cron"]
    assert due.succeeded == 1
    assert due.errors == ()


def test_t_e2e_011_scheduler_rejects_conflicting_cron_timezone_metadata() -> None:
    scheduler = Scheduler(clock=MutableClock(_instant()))

    with pytest.raises(ValueError, match="must match CronTrigger timezone"):
        scheduler.add_schedule(
            id="conflicting-timezone",
            target=lambda: None,
            trigger=CronTrigger(
                "0 9 * * *",
                timezone=Timezone("Europe/Paris"),
            ),
            timezone=Timezone("UTC"),
        )


def test_t_e2e_012_skip_misfire_does_not_execute_late_occurrence() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="skip-late",
        target=lambda: calls.append("unexpected"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
        misfire=MisfirePolicy.skip(),
    )

    clock.advance(Duration.minutes(15))
    result = scheduler.run_pending()

    assert calls == []
    assert result.materialized_request_ids == ()
    assert result.executions == ()
    assert result.unsupported_policy_schedules == ()


def test_t_e2e_013_skip_policy_still_runs_inside_grace_period() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="graceful-late",
        target=lambda: calls.append("executed"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
        misfire=MisfirePolicy.skip(grace=GracePeriod.seconds(10 * 60)),
    )

    clock.advance(Duration.minutes(15))
    result = scheduler.run_pending()

    assert calls == ["executed"]
    assert len(result.materialized_request_ids) == 1
    assert result.succeeded == 1


def test_t_e2e_014_explicit_run_now_executes_true_misfire() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="run-late",
        target=lambda: calls.append("executed"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
        misfire=MisfirePolicy.run_now(grace=GracePeriod.seconds(30)),
    )

    clock.advance(Duration.minutes(15))
    result = scheduler.run_pending()

    assert calls == ["executed"]
    assert len(result.materialized_request_ids) == 1
    assert result.succeeded == 1


def test_t_e2e_015_catch_up_drains_bounded_backlog_across_cycles() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[int] = []

    scheduler.add_schedule(
        id="catch-up",
        target=lambda: calls.append(len(calls) + 1),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
        misfire=MisfirePolicy.catch_up(max_occurrences=2),
    )

    clock.advance(Duration.minutes(45))

    first = scheduler.run_pending()
    second = scheduler.run_pending()
    third = scheduler.run_pending()

    assert len(first.materialized_request_ids) == 2
    assert len(second.materialized_request_ids) == 2
    assert third.materialized_request_ids == ()
    assert calls == [1, 2, 3, 4]
    assert first.succeeded == 2
    assert second.succeeded == 2
    assert first.recovery_limit_schedules == ()
    assert second.recovery_limit_schedules == ()


def test_t_e2e_016_coalesce_executes_only_latest_due_occurrence() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="coalesce",
        target=lambda: calls.append("executed"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
        misfire=MisfirePolicy.coalesce(max_occurrences=10),
    )

    clock.advance(Duration.minutes(45))
    result = scheduler.run_pending()

    assert calls == ["executed"]
    assert len(result.materialized_request_ids) == 1
    assert result.succeeded == 1
    assert result.recovery_limit_schedules == ()


def test_t_e2e_017_coalesce_fails_closed_when_backlog_exceeds_bound() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[str] = []

    scheduler.add_schedule(
        id="bounded-coalesce",
        target=lambda: calls.append("unexpected"),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
        misfire=MisfirePolicy.coalesce(max_occurrences=2),
    )

    clock.advance(Duration.minutes(45))
    result = scheduler.run_pending()

    assert calls == []
    assert result.materialized_request_ids == ()
    assert result.executions == ()
    assert result.recovery_limit_schedules == (ScheduleId("bounded-coalesce"),)


def test_t_e2e_018_concurrency_queue_serializes_catch_up_execution() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[int] = []

    scheduler.add_schedule(
        id="serialized-catch-up",
        target=lambda: calls.append(len(calls) + 1),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
        misfire=MisfirePolicy.catch_up(max_occurrences=2),
        concurrency=ConcurrencyPolicy.limit(max_instances=1),
    )

    clock.advance(Duration.minutes(25))

    first = scheduler.run_pending()

    assert len(first.materialized_request_ids) == 2
    assert calls == [1]
    assert first.succeeded == 1
    assert len(first.queued_request_ids) == 1
    assert first.dropped_request_ids == ()

    second = scheduler.run_pending()

    assert second.materialized_request_ids == ()
    assert calls == [1, 2]
    assert second.succeeded == 1
    assert second.queued_request_ids == ()
    assert second.dropped_request_ids == ()


def test_t_e2e_019_concurrency_drop_discards_overflow_catch_up_request() -> None:
    clock = MutableClock(_instant())
    scheduler = Scheduler(clock=clock)
    calls: list[int] = []

    scheduler.add_schedule(
        id="dropping-catch-up",
        target=lambda: calls.append(len(calls) + 1),
        trigger=IntervalTrigger(
            every=Duration.minutes(10),
            anchor=_instant(hour=10, minute=10),
        ),
        misfire=MisfirePolicy.catch_up(max_occurrences=2),
        concurrency=ConcurrencyPolicy.limit(
            max_instances=1,
            overflow=ConcurrencyOverflowPolicy.DROP,
        ),
    )

    clock.advance(Duration.minutes(25))

    first = scheduler.run_pending()

    assert len(first.materialized_request_ids) == 2
    assert calls == [1]
    assert first.succeeded == 1
    assert first.queued_request_ids == ()
    assert len(first.dropped_request_ids) == 1

    second = scheduler.run_pending()

    assert second.materialized_request_ids == ()
    assert calls == [1]
    assert second.executions == ()
