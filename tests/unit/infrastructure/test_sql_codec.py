"""LOT-21 unit tests for SQL persistence codecs."""

from datetime import UTC, datetime

from pyschedulekit.domain.concurrency import (
    ConcurrencyOverflowPolicy,
    ConcurrencyPolicy,
)
from pyschedulekit.domain.misfire import MisfirePolicy
from pyschedulekit.domain.retry import ExponentialBackoff, RetryPolicy
from pyschedulekit.domain.schedule import ScheduleDefinition, TargetRef
from pyschedulekit.domain.time import Duration, GracePeriod, Instant, Timezone
from pyschedulekit.domain.triggers import (
    CronAmbiguousTimePolicy,
    CronNonexistentTimePolicy,
    CronTrigger,
    DateTrigger,
    IntervalTrigger,
)
from pyschedulekit.infrastructure.sql_codec import (
    decode_schedule_definition,
    encode_schedule_definition,
)


def _instant(hour: int = 10) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, tzinfo=UTC))


def test_t_sql_codec_001_interval_definition_round_trip() -> None:
    definition = ScheduleDefinition(
        target=TargetRef.python("jobs:interval"),
        trigger=IntervalTrigger(
            every=Duration.minutes(5),
            anchor=_instant(),
        ),
        timezone=Timezone("Europe/Paris"),
        misfire=MisfirePolicy.catch_up(
            grace=GracePeriod.seconds(30),
            max_occurrences=7,
        ),
        concurrency=ConcurrencyPolicy.limit(
            max_instances=2,
            overflow=ConcurrencyOverflowPolicy.DROP,
        ),
        retry=RetryPolicy(
            max_attempts=4,
            backoff=ExponentialBackoff(
                initial_delay=Duration.seconds(2),
                multiplier=3,
                max_delay=Duration.seconds(20),
            ),
            retryable_categories=frozenset(("timeout", "transient")),
        ),
        timeout=Duration.seconds(45),
    )

    decoded = decode_schedule_definition(encode_schedule_definition(definition))

    assert decoded == definition


def test_t_sql_codec_002_date_trigger_round_trip() -> None:
    definition = ScheduleDefinition(
        target=TargetRef.workflow("workflow:once"),
        trigger=DateTrigger(at=_instant(hour=11)),
    )

    decoded = decode_schedule_definition(encode_schedule_definition(definition))

    assert decoded == definition


def test_t_sql_codec_003_cron_trigger_round_trip() -> None:
    definition = ScheduleDefinition(
        target=TargetRef.http("https://example.test/job"),
        trigger=CronTrigger(
            expression="15 8 * * 1-5",
            timezone=Timezone("Europe/Paris"),
            ambiguous_time=CronAmbiguousTimePolicy.SECOND,
            nonexistent_time=CronNonexistentTimePolicy.RAISE,
        ),
        timezone=Timezone("Europe/Paris"),
    )

    decoded = decode_schedule_definition(encode_schedule_definition(definition))

    assert decoded == definition
