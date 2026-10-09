"""LOT-21 unit tests for SQL persistence codecs."""

import json
from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.calendar import (
    CalendarRef,
    CalendarRevision,
    CalendarSnapshotRef,
)
from pyschedulekit.domain.concurrency import (
    ConcurrencyOverflowPolicy,
    ConcurrencyPolicy,
)
from pyschedulekit.domain.misfire import MisfirePolicy
from pyschedulekit.domain.retry import ExponentialBackoff, RetryPolicy
from pyschedulekit.domain.schedule import ScheduleDefinition, TargetRef
from pyschedulekit.domain.time import Duration, GracePeriod, Instant, Timezone
from pyschedulekit.domain.triggers import (
    AnyOfTrigger,
    BusinessDayTrigger,
    CronAmbiguousTimePolicy,
    CronNonexistentTimePolicy,
    CronTrigger,
    DateTrigger,
    IntervalTrigger,
)
from pyschedulekit.infrastructure.sql_codec import (
    decode_schedule_definition,
    encode_schedule_definition,
    migrate_schedule_definition_json,
)


def _instant(hour: int = 10) -> Instant:
    return Instant(datetime(2026, 1, 1, hour, tzinfo=UTC))


def _legacy_v2_json(definition: ScheduleDefinition) -> str:
    encoded = json.loads(encode_schedule_definition(definition))
    trigger = encoded["payload"]["trigger"]
    encoded["version"] = 2
    encoded["payload"]["trigger"] = {
        "kind": trigger["kind"],
        **trigger["config"],
    }
    return json.dumps(encoded)


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

    encoded = encode_schedule_definition(definition)
    decoded = decode_schedule_definition(encoded)

    assert json.loads(encoded)["version"] == 3
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


def test_calendar_snapshot_definition_round_trip() -> None:
    definition = ScheduleDefinition(
        target=TargetRef.python("jobs:calendar"),
        trigger=IntervalTrigger(
            every=Duration.days(1),
            anchor=_instant(),
        ),
        calendar=CalendarSnapshotRef(
            calendar_ref=CalendarRef("fr-business-days"),
            revision=CalendarRevision(4),
        ),
    )

    decoded = decode_schedule_definition(encode_schedule_definition(definition))

    assert decoded == definition
    assert decoded.calendar == CalendarSnapshotRef(
        calendar_ref=CalendarRef("fr-business-days"),
        revision=CalendarRevision(4),
    )


def test_legacy_v1_schedule_definition_without_calendar_remains_readable() -> None:
    definition = ScheduleDefinition(
        target=TargetRef.python("jobs:legacy"),
        trigger=IntervalTrigger(
            every=Duration.minutes(15),
            anchor=_instant(),
        ),
    )
    encoded = json.loads(_legacy_v2_json(definition))
    assert encoded["version"] == 2
    encoded["version"] = 1
    del encoded["payload"]["calendar"]

    decoded = decode_schedule_definition(json.dumps(encoded))

    assert decoded == definition
    assert decoded.calendar is None


def test_v1_schedule_definition_cannot_smuggle_calendar_binding() -> None:
    definition = ScheduleDefinition(
        target=TargetRef.python("jobs:legacy"),
        trigger=IntervalTrigger(
            every=Duration.minutes(15),
            anchor=_instant(),
        ),
    )
    encoded = json.loads(encode_schedule_definition(definition))
    encoded["version"] = 1

    with pytest.raises(ValueError, match="v1 must not contain a calendar binding"):
        decode_schedule_definition(json.dumps(encoded))


def test_future_schedule_definition_codec_version_fails_closed() -> None:
    definition = ScheduleDefinition(
        target=TargetRef.python("jobs:future"),
        trigger=IntervalTrigger(
            every=Duration.minutes(15),
            anchor=_instant(),
        ),
    )
    encoded = json.loads(encode_schedule_definition(definition))
    encoded["version"] = 4

    with pytest.raises(ValueError, match="Unsupported Schedule definition codec version"):
        decode_schedule_definition(json.dumps(encoded))


def test_business_day_trigger_definition_round_trip() -> None:
    definition = ScheduleDefinition(
        target=TargetRef.python("jobs:month-close"),
        trigger=BusinessDayTrigger(
            ordinal=-1,
            hour=18,
            minute=30,
            ambiguous_time=CronAmbiguousTimePolicy.SECOND,
            nonexistent_time=CronNonexistentTimePolicy.RAISE,
        ),
        timezone=Timezone("Europe/Paris"),
        calendar=CalendarSnapshotRef(
            calendar_ref=CalendarRef("finance-days"),
            revision=CalendarRevision(7),
        ),
    )

    encoded = encode_schedule_definition(definition)
    decoded = decode_schedule_definition(encoded)

    assert json.loads(encoded)["version"] == 3
    assert decoded == definition


def test_any_of_trigger_definition_round_trip_uses_versioned_child_envelopes() -> None:
    definition = ScheduleDefinition(
        target=TargetRef.python("jobs:composite"),
        trigger=AnyOfTrigger(
            DateTrigger(at=_instant(hour=11)),
            IntervalTrigger(every=Duration.hours(2), anchor=_instant()),
            CronTrigger("30 8 * * 1-5", timezone=Timezone("UTC")),
        ),
    )

    encoded = encode_schedule_definition(definition)
    payload = json.loads(encoded)["payload"]["trigger"]

    assert payload["kind"] == "any_of"
    assert payload["schema_version"] == 1
    assert [child["kind"] for child in payload["config"]["children"]] == [
        "date",
        "interval",
        "cron",
    ]
    assert all(child["schema_version"] == 1 for child in payload["config"]["children"])
    assert decode_schedule_definition(encoded) == definition


def test_nested_any_of_payload_migrates_to_flat_canonical_children() -> None:
    definition = ScheduleDefinition(
        target=TargetRef.python("jobs:nested-composite"),
        trigger=AnyOfTrigger(
            DateTrigger(at=_instant(hour=10)),
            DateTrigger(at=_instant(hour=11)),
            DateTrigger(at=_instant(hour=12)),
        ),
    )
    encoded = json.loads(encode_schedule_definition(definition))
    children = encoded["payload"]["trigger"]["config"]["children"]
    encoded["payload"]["trigger"]["config"]["children"] = [
        {
            "kind": "any_of",
            "schema_version": 1,
            "config": {"children": children[:2]},
        },
        children[2],
    ]

    migrated = json.loads(migrate_schedule_definition_json(json.dumps(encoded)))
    migrated_children = migrated["payload"]["trigger"]["config"]["children"]

    assert [child["kind"] for child in migrated_children] == ["date", "date", "date"]
    assert decode_schedule_definition(json.dumps(migrated)) == definition


def test_any_of_migration_preserves_occurrence_semantics() -> None:
    definition = ScheduleDefinition(
        target=TargetRef.python("jobs:composite-semantics"),
        trigger=AnyOfTrigger(
            IntervalTrigger(every=Duration.minutes(10), anchor=_instant()),
            IntervalTrigger(every=Duration.minutes(15), anchor=_instant()),
        ),
    )
    encoded = encode_schedule_definition(definition)
    decoded = decode_schedule_definition(encoded)
    migrated = decode_schedule_definition(migrate_schedule_definition_json(encoded))
    references = tuple(
        Instant(datetime(2026, 1, 1, 10, minute, tzinfo=UTC))
        for minute in (0, 9, 10, 14, 15, 20, 30, 59)
    )

    assert isinstance(decoded.trigger, AnyOfTrigger)
    assert isinstance(migrated.trigger, AnyOfTrigger)
    assert [decoded.trigger.next_after(reference) for reference in references] == [
        migrated.trigger.next_after(reference) for reference in references
    ]


def test_any_of_codec_rejects_non_array_children() -> None:
    encoded = json.loads(
        encode_schedule_definition(
            ScheduleDefinition(
                target=TargetRef.python("jobs:malformed-composite"),
                trigger=AnyOfTrigger(
                    DateTrigger(at=_instant(hour=10)),
                    DateTrigger(at=_instant(hour=11)),
                ),
            )
        )
    )
    encoded["payload"]["trigger"]["config"]["children"] = {}

    with pytest.raises(ValueError, match="children must be an array"):
        decode_schedule_definition(json.dumps(encoded))


def test_any_of_codec_rejects_non_object_child_payload() -> None:
    encoded = json.loads(
        encode_schedule_definition(
            ScheduleDefinition(
                target=TargetRef.python("jobs:scalar-child"),
                trigger=AnyOfTrigger(
                    DateTrigger(at=_instant(hour=10)),
                    DateTrigger(at=_instant(hour=11)),
                ),
            )
        )
    )
    encoded["payload"]["trigger"]["config"]["children"][0] = "date"

    with pytest.raises(ValueError, match="payload objects"):
        decode_schedule_definition(json.dumps(encoded))


def test_any_of_codec_rejects_fewer_than_two_children() -> None:
    encoded = json.loads(
        encode_schedule_definition(
            ScheduleDefinition(
                target=TargetRef.python("jobs:single-child"),
                trigger=AnyOfTrigger(
                    DateTrigger(at=_instant(hour=10)),
                    DateTrigger(at=_instant(hour=11)),
                ),
            )
        )
    )
    children = encoded["payload"]["trigger"]["config"]["children"]
    encoded["payload"]["trigger"]["config"]["children"] = children[:1]

    with pytest.raises(ValueError, match="at least two"):
        decode_schedule_definition(json.dumps(encoded))


def test_any_of_codec_rejects_calendar_aware_child() -> None:
    encoded = json.loads(
        encode_schedule_definition(
            ScheduleDefinition(
                target=TargetRef.python("jobs:calendar-child"),
                trigger=AnyOfTrigger(
                    DateTrigger(at=_instant(hour=10)),
                    DateTrigger(at=_instant(hour=11)),
                ),
            )
        )
    )
    encoded["payload"]["trigger"]["config"]["children"][1] = {
        "kind": "business_day",
        "schema_version": 1,
        "config": {
            "ordinal": 1,
            "hour": 9,
            "minute": 0,
            "ambiguous_time": "first",
            "nonexistent_time": "skip",
        },
    }

    with pytest.raises(ValueError, match="pure temporal"):
        decode_schedule_definition(json.dumps(encoded))


def test_any_of_codec_rejects_more_than_64_flattened_children() -> None:
    encoded = json.loads(
        encode_schedule_definition(
            ScheduleDefinition(
                target=TargetRef.python("jobs:too-many-children"),
                trigger=AnyOfTrigger(
                    DateTrigger(at=_instant(hour=10)),
                    DateTrigger(at=_instant(hour=11)),
                ),
            )
        )
    )
    child = encoded["payload"]["trigger"]["config"]["children"][0]
    encoded["payload"]["trigger"]["config"]["children"] = [child] * 65

    with pytest.raises(ValueError, match="at most 64"):
        decode_schedule_definition(json.dumps(encoded))


def test_any_of_codec_rejects_unversioned_child_payload() -> None:
    encoded = json.loads(
        encode_schedule_definition(
            ScheduleDefinition(
                target=TargetRef.python("jobs:unversioned-child"),
                trigger=AnyOfTrigger(
                    DateTrigger(at=_instant(hour=10)),
                    DateTrigger(at=_instant(hour=11)),
                ),
            )
        )
    )
    child = encoded["payload"]["trigger"]["config"]["children"][0]
    encoded["payload"]["trigger"]["config"]["children"][0] = {
        "kind": child["kind"],
        **child["config"],
    }

    with pytest.raises(ValueError, match="requires a versioned Trigger payload"):
        decode_schedule_definition(json.dumps(encoded))


def test_any_of_codec_rejects_future_child_version() -> None:
    encoded = json.loads(
        encode_schedule_definition(
            ScheduleDefinition(
                target=TargetRef.python("jobs:future-child"),
                trigger=AnyOfTrigger(
                    DateTrigger(at=_instant(hour=10)),
                    DateTrigger(at=_instant(hour=11)),
                ),
            )
        )
    )
    encoded["payload"]["trigger"]["config"]["children"][1]["schema_version"] = 2

    with pytest.raises(ValueError, match="Unsupported Trigger codec version"):
        decode_schedule_definition(json.dumps(encoded))


def test_any_of_codec_rejects_unknown_config_fields() -> None:
    encoded = json.loads(
        encode_schedule_definition(
            ScheduleDefinition(
                target=TargetRef.python("jobs:unknown-field"),
                trigger=AnyOfTrigger(
                    DateTrigger(at=_instant(hour=10)),
                    DateTrigger(at=_instant(hour=11)),
                ),
            )
        )
    )
    encoded["payload"]["trigger"]["config"]["future"] = True

    with pytest.raises(ValueError, match="exactly the children field"):
        decode_schedule_definition(json.dumps(encoded))


def test_any_of_codec_rejects_payload_beyond_nesting_limit() -> None:
    encoded = json.loads(
        encode_schedule_definition(
            ScheduleDefinition(
                target=TargetRef.python("jobs:deep-composite"),
                trigger=AnyOfTrigger(
                    DateTrigger(at=_instant(hour=10)),
                    DateTrigger(at=_instant(hour=11)),
                ),
            )
        )
    )
    leaf = encoded["payload"]["trigger"]["config"]["children"][0]
    nested = encoded["payload"]["trigger"]["config"]["children"][1]
    for _ in range(17):
        nested = {
            "kind": "any_of",
            "schema_version": 1,
            "config": {"children": [leaf, nested]},
        }
    encoded["payload"]["trigger"] = nested

    with pytest.raises(ValueError, match="nesting depth"):
        decode_schedule_definition(json.dumps(encoded))


@pytest.mark.parametrize(
    "definition",
    (
        ScheduleDefinition(
            target=TargetRef.python("jobs:legacy-date"),
            trigger=DateTrigger(at=_instant(hour=11)),
        ),
        ScheduleDefinition(
            target=TargetRef.python("jobs:legacy-interval"),
            trigger=IntervalTrigger(
                every=Duration.minutes(15),
                anchor=_instant(),
            ),
        ),
        ScheduleDefinition(
            target=TargetRef.python("jobs:legacy-cron"),
            trigger=CronTrigger(
                expression="15 8 * * 1-5",
                timezone=Timezone("Europe/Paris"),
            ),
            timezone=Timezone("Europe/Paris"),
        ),
        ScheduleDefinition(
            target=TargetRef.python("jobs:legacy-business-day"),
            trigger=BusinessDayTrigger(ordinal=-1, hour=18),
            calendar=CalendarSnapshotRef(
                calendar_ref=CalendarRef("finance-days"),
                revision=CalendarRevision(2),
            ),
        ),
    ),
)
def test_legacy_v2_flat_trigger_payloads_remain_readable(
    definition: ScheduleDefinition,
) -> None:
    decoded = decode_schedule_definition(_legacy_v2_json(definition))

    assert decoded == definition


def test_supported_legacy_definition_migrates_to_v3_trigger_envelope() -> None:
    definition = ScheduleDefinition(
        target=TargetRef.python("jobs:migrate"),
        trigger=IntervalTrigger(
            every=Duration.minutes(15),
            anchor=_instant(),
        ),
        calendar=CalendarSnapshotRef(
            calendar_ref=CalendarRef("business-days"),
            revision=CalendarRevision(3),
        ),
    )

    migrated = json.loads(migrate_schedule_definition_json(_legacy_v2_json(definition)))

    assert migrated["version"] == 3
    assert migrated["payload"]["trigger"] == {
        "kind": "interval",
        "schema_version": 1,
        "config": {
            "every_seconds": 900.0,
            "anchor": _instant().value.isoformat(),
        },
    }
    assert decode_schedule_definition(json.dumps(migrated)) == definition


def test_v3_requires_versioned_trigger_payload() -> None:
    definition = ScheduleDefinition(
        target=TargetRef.python("jobs:malformed-v3"),
        trigger=IntervalTrigger(
            every=Duration.minutes(15),
            anchor=_instant(),
        ),
    )
    encoded = json.loads(encode_schedule_definition(definition))
    trigger = encoded["payload"]["trigger"]
    encoded["payload"]["trigger"] = {
        "kind": trigger["kind"],
        **trigger["config"],
    }

    with pytest.raises(ValueError, match="v3 requires a versioned Trigger payload"):
        decode_schedule_definition(json.dumps(encoded))


def test_future_trigger_codec_version_fails_closed() -> None:
    definition = ScheduleDefinition(
        target=TargetRef.python("jobs:future-trigger"),
        trigger=IntervalTrigger(
            every=Duration.minutes(15),
            anchor=_instant(),
        ),
    )
    encoded = json.loads(encode_schedule_definition(definition))
    encoded["payload"]["trigger"]["schema_version"] = 2

    with pytest.raises(ValueError, match="Unsupported Trigger codec version"):
        decode_schedule_definition(json.dumps(encoded))


def test_v2_to_v3_migration_preserves_cron_occurrence_semantics() -> None:
    definition = ScheduleDefinition(
        target=TargetRef.python("jobs:semantic-parity"),
        trigger=CronTrigger(
            expression="15 8 * * 1-5",
            timezone=Timezone("Europe/Paris"),
            ambiguous_time=CronAmbiguousTimePolicy.SECOND,
            nonexistent_time=CronNonexistentTimePolicy.RAISE,
        ),
        timezone=Timezone("Europe/Paris"),
    )
    legacy = decode_schedule_definition(_legacy_v2_json(definition))
    migrated = decode_schedule_definition(
        migrate_schedule_definition_json(_legacy_v2_json(definition))
    )
    references = (
        Instant.parse("2026-01-01T00:00:00+00:00"),
        Instant.parse("2026-03-27T20:00:00+00:00"),
        Instant.parse("2026-10-23T20:00:00+00:00"),
        Instant.parse("2026-12-31T23:00:00+00:00"),
    )

    assert isinstance(legacy.trigger, CronTrigger)
    assert isinstance(migrated.trigger, CronTrigger)
    assert [legacy.trigger.next_after(reference) for reference in references] == [
        migrated.trigger.next_after(reference) for reference in references
    ]
