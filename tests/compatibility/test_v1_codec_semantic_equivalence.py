"""V1-02.D codec migration and semantic-equivalence qualification."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from pyschedulekit.domain.calendar import (
    BusinessCalendar,
    CalendarRef,
    CalendarRevision,
)
from pyschedulekit.domain.concurrency import (
    ConcurrencyEvaluator,
    ConcurrencyOverflowPolicy,
    ConcurrencyPolicy,
)
from pyschedulekit.domain.execution import (
    AttemptResult,
    AttemptState,
    ExecutionPolicySnapshot,
    ExecutionResult,
    ExecutionState,
    Failure,
    FailureCategory,
)
from pyschedulekit.domain.retry import (
    ExponentialBackoff,
    RetryEvaluator,
    RetryPolicy,
)
from pyschedulekit.domain.time import Duration, Instant, Timezone
from pyschedulekit.domain.trigger import CalendarAwareTrigger, Trigger
from pyschedulekit.domain.triggers import AnyOfTrigger, BusinessDayTrigger
from pyschedulekit.infrastructure.calendar_codec import (
    decode_business_calendar,
    decode_business_calendar_collection,
    encode_business_calendar,
    encode_business_calendar_collection,
)
from pyschedulekit.infrastructure.persistence_versions import (
    CALENDAR_COLLECTION_CODEC_VERSION,
    CALENDAR_VALUE_CODEC_VERSION,
    SCHEDULE_DEFINITION_CODEC_VERSION,
    SQL_VALUE_CODEC_VERSION,
    TRIGGER_CODEC_VERSION,
)
from pyschedulekit.infrastructure.sql_codec import (
    decode_attempt_result,
    decode_concurrency_policy,
    decode_execution_policy_snapshot,
    decode_execution_result,
    decode_retry_policy,
    decode_schedule_definition,
    encode_attempt_result,
    encode_concurrency_policy,
    encode_execution_policy_snapshot,
    encode_execution_result,
    encode_retry_policy,
    encode_schedule_definition,
    migrate_schedule_definition_json,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "persistence" / "v1"
RELEASED = "released/v0.1.0a3"
PRE1 = "pre1/945ec1732fc03419f4d82bd81750bf7bf1032fd6"

SCHEDULE_FIXTURES = {
    1: f"{RELEASED}/schedule_definition_v1_interval.json",
    2: f"{PRE1}/schedule_definition_v2_business_day.json",
    3: f"{PRE1}/schedule_definition_v3_composite.json",
}


def _fixture(relative_path: str) -> str:
    return (FIXTURE_ROOT / relative_path).read_text(encoding="utf-8")


def _instant(value: str) -> Instant:
    return Instant.parse(value)


def _temporal_trace(
    trigger: Trigger,
    references: tuple[Instant, ...],
) -> tuple[Instant | None, ...]:
    return tuple(trigger.next_after(reference) for reference in references)


def _business_day_trace(
    trigger: BusinessDayTrigger,
    references: tuple[Instant, ...],
    *,
    calendar: BusinessCalendar,
    timezone: Timezone,
) -> tuple[Instant, ...]:
    return tuple(
        trigger.next_after_with_calendar(
            reference,
            timezone=timezone,
            calendar=calendar,
        )
        for reference in references
    )


@pytest.mark.parametrize("version", (1, 2, 3))
def test_v1_02d_schedule_definition_migration_is_domain_equivalent(version: int) -> None:
    source_text = _fixture(SCHEDULE_FIXTURES[version])
    source = decode_schedule_definition(source_text)

    migrated_text = migrate_schedule_definition_json(source_text)
    migrated_payload = json.loads(migrated_text)
    migrated = decode_schedule_definition(migrated_text)

    assert migrated == source
    assert migrated_payload["version"] == SCHEDULE_DEFINITION_CODEC_VERSION
    assert migrated_payload["payload"]["trigger"]["schema_version"] == TRIGGER_CODEC_VERSION
    assert migrated_text == encode_schedule_definition(source)
    assert migrate_schedule_definition_json(migrated_text) == migrated_text


def test_v1_02d_v1_interval_occurrence_semantics_survive_v3_migration() -> None:
    source_text = _fixture(SCHEDULE_FIXTURES[1])
    before = decode_schedule_definition(source_text)
    after = decode_schedule_definition(migrate_schedule_definition_json(source_text))

    assert isinstance(before.trigger, Trigger)
    assert isinstance(after.trigger, Trigger)
    assert not isinstance(before.trigger, CalendarAwareTrigger)
    assert not isinstance(after.trigger, CalendarAwareTrigger)

    references = tuple(
        _instant(value)
        for value in (
            "2026-01-01T09:59:59+00:00",
            "2026-01-01T10:00:00+00:00",
            "2026-01-01T10:04:59+00:00",
            "2026-01-01T10:05:00+00:00",
            "2026-01-01T11:02:00+00:00",
        )
    )
    assert _temporal_trace(before.trigger, references) == _temporal_trace(after.trigger, references)


def test_v1_02d_v2_business_day_semantics_survive_v3_migration() -> None:
    source_text = _fixture(SCHEDULE_FIXTURES[2])
    before = decode_schedule_definition(source_text)
    after = decode_schedule_definition(migrate_schedule_definition_json(source_text))

    assert isinstance(before.trigger, BusinessDayTrigger)
    assert isinstance(after.trigger, BusinessDayTrigger)
    assert before.calendar == after.calendar
    assert before.calendar is not None

    calendar = BusinessCalendar(
        calendar_ref=CalendarRef("finance-days"),
        revision=CalendarRevision(7),
        working_weekdays=frozenset({0, 1, 2, 3, 4}),
        holidays=frozenset({date(2026, 1, 1), date(2026, 12, 25)}),
        extra_working_days=frozenset({date(2026, 1, 31)}),
    )
    references = tuple(
        _instant(value)
        for value in (
            "2026-01-01T00:00:00+00:00",
            "2026-01-30T18:00:00+00:00",
            "2026-02-01T00:00:00+00:00",
            "2026-03-15T12:00:00+00:00",
            "2026-10-20T12:00:00+00:00",
        )
    )

    assert _business_day_trace(
        before.trigger,
        references,
        calendar=calendar,
        timezone=before.timezone,
    ) == _business_day_trace(
        after.trigger,
        references,
        calendar=calendar,
        timezone=after.timezone,
    )


def test_v1_02d_v3_composite_trigger_semantics_are_idempotent() -> None:
    source_text = _fixture(SCHEDULE_FIXTURES[3])
    before = decode_schedule_definition(source_text)
    migrated_text = migrate_schedule_definition_json(source_text)
    after = decode_schedule_definition(migrated_text)

    assert isinstance(before.trigger, AnyOfTrigger)
    assert isinstance(after.trigger, AnyOfTrigger)
    references = tuple(
        _instant(value)
        for value in (
            "2026-01-01T07:00:00+00:00",
            "2026-01-01T08:30:00+00:00",
            "2026-01-01T10:00:00+00:00",
            "2026-01-01T10:59:59+00:00",
            "2026-01-01T11:00:00+00:00",
            "2026-01-02T07:00:00+00:00",
        )
    )

    assert _temporal_trace(before.trigger, references) == _temporal_trace(after.trigger, references)
    assert migrated_text == source_text.rstrip("\n")


def test_v1_02d_released_sql_value_fixtures_preserve_behavior() -> None:
    retry_source = decode_retry_policy(_fixture(f"{RELEASED}/retry_policy_v1_exponential.json"))
    result_source = decode_execution_result(
        _fixture(f"{RELEASED}/execution_result_v1_failure.json")
    )

    retry_roundtrip = decode_retry_policy(encode_retry_policy(retry_source))
    result_roundtrip = decode_execution_result(encode_execution_result(result_source))

    assert retry_roundtrip == retry_source
    assert result_roundtrip == result_source
    assert result_source is not None
    assert result_source.failure is not None

    evaluator = RetryEvaluator()
    source_decisions = tuple(
        evaluator.evaluate(
            policy=retry_source,
            attempt_number=attempt,
            failure=result_source.failure,
        )
        for attempt in range(1, retry_source.max_attempts + 1)
    )
    roundtrip_decisions = tuple(
        evaluator.evaluate(
            policy=retry_roundtrip,
            attempt_number=attempt,
            failure=result_source.failure,
        )
        for attempt in range(1, retry_roundtrip.max_attempts + 1)
    )
    assert roundtrip_decisions == source_decisions


def test_v1_02d_all_generic_sql_value_codecs_are_semantically_stable() -> None:
    retry = RetryPolicy(
        max_attempts=5,
        backoff=ExponentialBackoff(
            initial_delay=Duration.seconds(3),
            multiplier=2.5,
            max_delay=Duration.seconds(30),
        ),
        retryable_categories=frozenset({"timeout", "transient"}),
    )
    concurrency = ConcurrencyPolicy.limit(
        max_instances=2,
        overflow=ConcurrencyOverflowPolicy.DROP,
    )
    execution_policy = ExecutionPolicySnapshot(
        timeout=Duration.seconds(42),
        retry=retry,
    )
    failure = Failure(
        category=FailureCategory.TRANSIENT,
        code="upstream.unavailable",
        message="upstream unavailable",
        occurred_at=_instant("2026-04-01T09:59:59+00:00"),
        retryable_hint=None,
        details=(("service", "billing"), ("region", "eu-west")),
    )
    attempt_result = AttemptResult(
        state=AttemptState.FAILED,
        completed_at=_instant("2026-04-01T10:00:00+00:00"),
        failure=failure,
    )
    execution_result = ExecutionResult(
        state=ExecutionState.FAILED,
        completed_at=_instant("2026-04-01T10:00:00+00:00"),
        failure=failure,
    )

    retry_after = decode_retry_policy(encode_retry_policy(retry))
    concurrency_after = decode_concurrency_policy(encode_concurrency_policy(concurrency))
    execution_policy_after = decode_execution_policy_snapshot(
        encode_execution_policy_snapshot(execution_policy)
    )
    attempt_after = decode_attempt_result(encode_attempt_result(attempt_result))
    execution_after = decode_execution_result(encode_execution_result(execution_result))

    assert retry_after == retry
    assert concurrency_after == concurrency
    assert execution_policy_after == execution_policy
    assert attempt_after == attempt_result
    assert execution_after == execution_result

    concurrency_evaluator = ConcurrencyEvaluator()
    assert tuple(
        concurrency_evaluator.evaluate(policy=concurrency, active_instances=count)
        for count in range(4)
    ) == tuple(
        concurrency_evaluator.evaluate(policy=concurrency_after, active_instances=count)
        for count in range(4)
    )

    retry_evaluator = RetryEvaluator()
    assert tuple(
        retry_evaluator.evaluate(policy=retry, attempt_number=attempt, failure=failure)
        for attempt in range(1, retry.max_attempts + 1)
    ) == tuple(
        retry_evaluator.evaluate(
            policy=retry_after,
            attempt_number=attempt,
            failure=failure,
        )
        for attempt in range(1, retry_after.max_attempts + 1)
    )

    for encoded in (
        encode_retry_policy(retry),
        encode_concurrency_policy(concurrency),
        encode_execution_policy_snapshot(execution_policy),
        encode_attempt_result(attempt_result),
        encode_execution_result(execution_result),
    ):
        assert encoded is not None
        assert json.loads(encoded)["version"] == SQL_VALUE_CODEC_VERSION


def test_v1_02d_calendar_value_semantics_survive_round_trip() -> None:
    source = decode_business_calendar(_fixture(f"{PRE1}/calendar_value_v1.json"))
    after = decode_business_calendar(encode_business_calendar(source))

    assert after == source
    sample_start = date(2026, 4, 27)
    sample_days = tuple(sample_start + timedelta(days=offset) for offset in range(14))
    assert tuple(source.is_working_day(day) for day in sample_days) == tuple(
        after.is_working_day(day) for day in sample_days
    )
    assert json.loads(encode_business_calendar(source))["schema_version"] == (
        CALENDAR_VALUE_CODEC_VERSION
    )


def test_v1_02d_calendar_collection_semantics_survive_round_trip() -> None:
    source = decode_business_calendar_collection(
        _fixture(f"{PRE1}/calendar_collection_v1.json")
    )
    after = decode_business_calendar_collection(encode_business_calendar_collection(source))

    assert after == source
    assert [
        (calendar.calendar_ref.value, calendar.revision.value)
        for calendar in after
    ] == [
        ("finance-days", 2),
        ("market", 1),
    ]
    assert json.loads(encode_business_calendar_collection(source))["schema_version"] == (
        CALENDAR_COLLECTION_CODEC_VERSION
    )


def test_v1_02d_current_codec_version_matrix_is_explicit() -> None:
    assert {
        "sql-value": SQL_VALUE_CODEC_VERSION,
        "schedule-definition": SCHEDULE_DEFINITION_CODEC_VERSION,
        "trigger-envelope": TRIGGER_CODEC_VERSION,
        "calendar-value": CALENDAR_VALUE_CODEC_VERSION,
        "calendar-collection": CALENDAR_COLLECTION_CODEC_VERSION,
    } == {
        "sql-value": 1,
        "schedule-definition": 3,
        "trigger-envelope": 1,
        "calendar-value": 1,
        "calendar-collection": 1,
    }
