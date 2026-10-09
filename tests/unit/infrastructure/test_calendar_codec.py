"""CAL-05 qualification for the strict BusinessCalendar provider codec."""

import json
from datetime import date

import pytest

from pyschedulekit.domain.calendar import BusinessCalendar, CalendarRef, CalendarRevision
from pyschedulekit.errors import PyScheduleKitConfigurationError
from pyschedulekit.infrastructure.calendar_codec import (
    decode_business_calendar,
    decode_business_calendar_collection,
    encode_business_calendar,
    encode_business_calendar_collection,
)


def _calendar(name: str = "market", revision: int = 1) -> BusinessCalendar:
    return BusinessCalendar(
        calendar_ref=CalendarRef(name),
        revision=CalendarRevision(revision),
        working_weekdays=frozenset({0, 1, 2, 3, 4, 5}),
        holidays=frozenset({date(2026, 5, 1)}),
        extra_working_days=frozenset({date(2026, 5, 3)}),
    )


def test_business_calendar_codec_round_trips_deterministically() -> None:
    calendar = _calendar()

    encoded = encode_business_calendar(calendar)
    decoded = decode_business_calendar(encoded)

    assert decoded == calendar
    assert json.loads(encoded) == {
        "schema_version": 1,
        "reference": "market",
        "revision": 1,
        "working_weekdays": [0, 1, 2, 3, 4, 5],
        "holidays": ["2026-05-01"],
        "extra_working_days": ["2026-05-03"],
    }


def test_collection_codec_sorts_revisions_deterministically() -> None:
    encoded = encode_business_calendar_collection(
        (
            _calendar("z", 2),
            _calendar("a", 3),
            _calendar("a", 1),
        )
    )

    decoded = decode_business_calendar_collection(encoded)

    assert [(item.calendar_ref.value, item.revision.value) for item in decoded] == [
        ("a", 1),
        ("a", 3),
        ("z", 2),
    ]


def test_calendar_codec_rejects_unknown_fields_and_future_versions() -> None:
    payload = json.loads(encode_business_calendar(_calendar()))
    payload["unknown"] = True

    with pytest.raises(PyScheduleKitConfigurationError, match="unknown"):
        decode_business_calendar(json.dumps(payload))

    payload.pop("unknown")
    payload["schema_version"] = 2

    with pytest.raises(PyScheduleKitConfigurationError, match="schema version"):
        decode_business_calendar(json.dumps(payload))


def test_calendar_codec_rejects_invalid_dates() -> None:
    payload = json.loads(encode_business_calendar(_calendar()))
    payload["holidays"] = ["2026-02-31"]

    with pytest.raises(PyScheduleKitConfigurationError, match="invalid ISO date"):
        decode_business_calendar(json.dumps(payload))


def test_collection_codec_rejects_duplicate_revisions() -> None:
    calendar = json.loads(encode_business_calendar(_calendar()))
    payload = {
        "schema_version": 1,
        "calendars": [calendar, calendar],
    }

    with pytest.raises(PyScheduleKitConfigurationError, match="duplicate revisions"):
        decode_business_calendar_collection(json.dumps(payload))
