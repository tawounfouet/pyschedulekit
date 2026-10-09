"""V1-01.B decisions for the primary root/API stable candidate surface."""

from pyschedulekit.api._manifest import (
    API_ONLY_V1_PUBLIC_NAMES,
    ROOT_V1_PUBLIC_NAMES,
    STABLE_PUBLIC_NAMES,
)


def test_v1_01b_root_and_api_only_sets_partition_primary_api() -> None:
    assert len(ROOT_V1_PUBLIC_NAMES) == 63
    assert len(API_ONLY_V1_PUBLIC_NAMES) == 41

    assert tuple(sorted(ROOT_V1_PUBLIC_NAMES)) == ROOT_V1_PUBLIC_NAMES
    assert tuple(sorted(API_ONLY_V1_PUBLIC_NAMES)) == API_ONLY_V1_PUBLIC_NAMES

    assert set(ROOT_V1_PUBLIC_NAMES).isdisjoint(API_ONLY_V1_PUBLIC_NAMES)
    assert set(ROOT_V1_PUBLIC_NAMES) | set(API_ONLY_V1_PUBLIC_NAMES) == set(
        STABLE_PUBLIC_NAMES
    )


def test_v1_01b_root_keeps_primary_user_intent_concepts() -> None:
    required = {
        "Scheduler",
        "TargetRef",
        "Trigger",
        "DateTrigger",
        "IntervalTrigger",
        "CronTrigger",
        "BusinessDayTrigger",
        "AnyOfTrigger",
        "MisfirePolicy",
        "ConcurrencyPolicy",
        "RetryPolicy",
        "CancellationToken",
        "ScheduleSnapshot",
        "ExecutionSnapshot",
        "RunPendingResult",
    }

    assert required <= set(ROOT_V1_PUBLIC_NAMES)


def test_v1_01b_advanced_extension_types_are_api_only() -> None:
    advanced = {
        "Clock",
        "CalendarProvider",
        "Executor",
        "ExecutorRegistry",
        "ObservationSink",
        "OutboxPublisher",
        "UnitOfWorkFactory",
        "WorkerId",
        "PreparedTarget",
    }

    assert advanced <= set(API_ONLY_V1_PUBLIC_NAMES)
