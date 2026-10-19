"""V1-02.B immutable golden compatibility fixtures."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from pyschedulekit.domain.retry import ExponentialBackoff
from pyschedulekit.domain.triggers import AnyOfTrigger, BusinessDayTrigger, IntervalTrigger
from pyschedulekit.infrastructure.calendar_codec import (
    decode_business_calendar,
    decode_business_calendar_collection,
    encode_business_calendar,
    encode_business_calendar_collection,
)
from pyschedulekit.infrastructure.sql_codec import (
    decode_execution_result,
    decode_retry_policy,
    decode_schedule_definition,
    encode_execution_result,
    encode_retry_policy,
    encode_schedule_definition,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "persistence" / "v1"
RELEASED = "released/v0.1.0a3"
PRE1 = "pre1/945ec1732fc03419f4d82bd81750bf7bf1032fd6"

EXPECTED_FIXTURE_HASHES = {
    f"{PRE1}/calendar_collection_v1.json": (
        "17109696cf2f136d0c365340ea78d6cb98b28c4bc6705b007f29b3b7876508da"
    ),
    f"{PRE1}/calendar_value_v1.json": (
        "78d789a85abac4a51f8cc64f04dc34ef962ab6fd209ba43131f44e4e5cf710b7"
    ),
    f"{PRE1}/schedule_definition_v2_business_day.json": (
        "4a1325547e20560d30a78133952a20edc0159ef7db4eead6f2e604af4d65a385"
    ),
    f"{PRE1}/schedule_definition_v3_composite.json": (
        "c187efe72bb900130b77000b7ab78cb9eea5c74ae37c462de2c920cf3a93f5d7"
    ),
    f"{RELEASED}/execution_result_v1_failure.json": (
        "62e46920b10b6792f4b01bd68b58c376fbd66283e4e6d203e92a40b40a8325d4"
    ),
    f"{RELEASED}/retry_policy_v1_exponential.json": (
        "cf01bac60d2a4702460a5affdf9c31d67ae2b5dc79133c68ef010dd56038ac25"
    ),
    f"{RELEASED}/schedule_definition_v1_interval.json": (
        "107b0dfa5e047fca52fd2135979691c49d24476ee2c5d0e9218ea8eabee846bb"
    ),
}


def _fixture(relative_path: str) -> str:
    return (FIXTURE_ROOT / relative_path).read_text(encoding="utf-8")


def test_v1_02b_fixture_inventory_and_hashes_are_immutable() -> None:
    manifest = json.loads(_fixture("manifest.json"))

    assert manifest["schema_version"] == 1
    assert manifest["policy"] == {
        "mutation": "append-only",
        "released_fixture_source": "immutable-release-ref",
        "pre1_fixture_source": "immutable-commit-sha",
        "database_fixture_scope": "V1-02.C",
    }
    assert manifest["fixture_sha256"] == EXPECTED_FIXTURE_HASHES

    actual = {
        path.relative_to(FIXTURE_ROOT).as_posix()
        for path in FIXTURE_ROOT.rglob("*.json")
        if path.name != "manifest.json"
    }
    assert actual == set(EXPECTED_FIXTURE_HASHES)

    for relative_path, expected_hash in EXPECTED_FIXTURE_HASHES.items():
        payload = (FIXTURE_ROOT / relative_path).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == expected_hash


def test_v1_02b_fixture_provenance_is_exact() -> None:
    manifest = json.loads(_fixture("manifest.json"))

    assert manifest["sources"]["released-v0.1.0a3"] == {
        "source_ref": "v0.1.0a3",
        "source_version": "0.1.0a3",
        "evidence": [
            "src/pyschedulekit/infrastructure/sql_codec.py",
            "tests/unit/infrastructure/test_sql_codec.py",
        ],
    }
    assert manifest["sources"]["pre1-945ec173"] == {
        "source_ref": "945ec1732fc03419f4d82bd81750bf7bf1032fd6",
        "source_version": "0.1.0a4",
        "evidence": [
            "src/pyschedulekit/infrastructure/sql_codec.py",
            "src/pyschedulekit/infrastructure/calendar_codec.py",
            "tests/unit/infrastructure/test_sql_codec.py",
            "tests/unit/infrastructure/test_calendar_codec.py",
        ],
    }


def test_released_v0_1_0a3_schedule_definition_fixture_remains_readable() -> None:
    definition = decode_schedule_definition(
        _fixture(f"{RELEASED}/schedule_definition_v1_interval.json")
    )

    assert definition.target.kind == "python"
    assert definition.target.reference == "jobs:interval"
    assert isinstance(definition.trigger, IntervalTrigger)
    assert definition.trigger.every.total_seconds == 300.0
    assert definition.trigger.anchor.value.isoformat() == "2026-01-01T10:00:00+00:00"
    assert definition.timezone.name == "Europe/Paris"
    assert definition.misfire.action.value == "catch_up"
    assert definition.misfire.grace.duration.total_seconds == 30.0
    assert definition.misfire.max_occurrences == 7
    assert definition.concurrency.mode.value == "limit"
    assert definition.concurrency.max_instances == 2
    assert definition.concurrency.overflow.value == "drop"
    assert definition.retry.max_attempts == 4
    assert isinstance(definition.retry.backoff, ExponentialBackoff)
    assert definition.retry.backoff.initial_delay.total_seconds == 2.0
    assert definition.retry.backoff.multiplier == 3
    assert definition.retry.backoff.max_delay is not None
    assert definition.retry.backoff.max_delay.total_seconds == 20.0
    assert definition.timeout is not None
    assert definition.timeout.total_seconds == 45.0
    assert definition.calendar is None


def test_released_v0_1_0a3_sql_value_fixtures_remain_readable() -> None:
    retry = decode_retry_policy(_fixture(f"{RELEASED}/retry_policy_v1_exponential.json"))
    result = decode_execution_result(_fixture(f"{RELEASED}/execution_result_v1_failure.json"))

    assert retry.max_attempts == 4
    assert retry.retryable_categories == frozenset({"timeout", "transient"})
    assert isinstance(retry.backoff, ExponentialBackoff)
    assert retry.backoff.initial_delay.total_seconds == 2.0
    assert retry.backoff.multiplier == 3

    assert result is not None
    assert result.state.value == "failed"
    assert result.completed_at.value.isoformat() == "2026-01-01T10:05:00+00:00"
    assert result.failure is not None
    assert result.failure.category.value == "transient"
    assert result.failure.code == "worker-unavailable"
    assert result.failure.retryable_hint is True
    assert result.failure.details == (("region", "eu-west"), ("worker", "worker-7"))


def test_pre1_schedule_definition_v2_fixture_remains_readable() -> None:
    definition = decode_schedule_definition(
        _fixture(f"{PRE1}/schedule_definition_v2_business_day.json")
    )

    assert definition.target.reference == "jobs:month-close"
    assert isinstance(definition.trigger, BusinessDayTrigger)
    assert definition.trigger.ordinal == -1
    assert definition.trigger.hour == 18
    assert definition.trigger.minute == 30
    assert definition.trigger.ambiguous_time.value == "second"
    assert definition.trigger.nonexistent_time.value == "raise"
    assert definition.calendar is not None
    assert definition.calendar.calendar_ref.value == "finance-days"
    assert definition.calendar.revision.value == 7


def test_pre1_schedule_definition_v3_trigger_envelopes_remain_readable() -> None:
    definition = decode_schedule_definition(
        _fixture(f"{PRE1}/schedule_definition_v3_composite.json")
    )

    assert definition.target.reference == "jobs:composite"
    assert isinstance(definition.trigger, AnyOfTrigger)
    assert len(definition.trigger.triggers) == 3
    assert [type(trigger).__name__ for trigger in definition.trigger.triggers] == [
        "DateTrigger",
        "IntervalTrigger",
        "CronTrigger",
    ]


def test_pre1_calendar_value_and_collection_fixtures_remain_readable() -> None:
    calendar = decode_business_calendar(_fixture(f"{PRE1}/calendar_value_v1.json"))
    calendars = decode_business_calendar_collection(
        _fixture(f"{PRE1}/calendar_collection_v1.json")
    )

    assert calendar.calendar_ref.value == "market"
    assert calendar.revision.value == 1
    assert calendar.working_weekdays == frozenset({0, 1, 2, 3, 4, 5})
    assert calendar.holidays == frozenset({date(2026, 5, 1)})
    assert calendar.extra_working_days == frozenset({date(2026, 5, 3)})

    assert [(item.calendar_ref.value, item.revision.value) for item in calendars] == [
        ("finance-days", 2),
        ("market", 1),
    ]


def test_unchanged_writers_reproduce_the_golden_bytes_exactly() -> None:
    retry_text = _fixture(f"{RELEASED}/retry_policy_v1_exponential.json")
    result_text = _fixture(f"{RELEASED}/execution_result_v1_failure.json")
    definition_text = _fixture(f"{PRE1}/schedule_definition_v3_composite.json")
    calendar_text = _fixture(f"{PRE1}/calendar_value_v1.json")
    collection_text = _fixture(f"{PRE1}/calendar_collection_v1.json")

    retry = decode_retry_policy(retry_text)
    result = decode_execution_result(result_text)
    definition = decode_schedule_definition(definition_text)
    calendar = decode_business_calendar(calendar_text)
    calendars = decode_business_calendar_collection(collection_text)

    assert encode_retry_policy(retry) + "\n" == retry_text
    assert result is not None
    assert encode_execution_result(result) + "\n" == result_text
    assert encode_schedule_definition(definition) + "\n" == definition_text
    assert encode_business_calendar(calendar) + "\n" == calendar_text
    assert encode_business_calendar_collection(calendars) + "\n" == collection_text
