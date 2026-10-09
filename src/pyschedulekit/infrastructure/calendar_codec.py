"""Strict versioned JSON codec for BusinessCalendar provider adapters."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, cast

from pyschedulekit.domain.calendar import (
    BusinessCalendar,
    CalendarRef,
    CalendarRevision,
)
from pyschedulekit.errors import PyScheduleKitConfigurationError

_CALENDAR_CODEC_VERSION = 1
_CALENDAR_COLLECTION_CODEC_VERSION = 1
_CALENDAR_FIELDS = frozenset(
    {
        "schema_version",
        "reference",
        "revision",
        "working_weekdays",
        "holidays",
        "extra_working_days",
    }
)
_COLLECTION_FIELDS = frozenset({"schema_version", "calendars"})


def encode_business_calendar(calendar: BusinessCalendar) -> str:
    """Serialize one exact BusinessCalendar revision deterministically."""

    return json.dumps(
        _encode_business_calendar_payload(calendar),
        separators=(",", ":"),
        sort_keys=True,
    )


def decode_business_calendar(value: str) -> BusinessCalendar:
    """Decode one strict versioned BusinessCalendar payload."""

    try:
        payload = cast(dict[str, Any], json.loads(value))
    except (TypeError, json.JSONDecodeError) as exc:
        raise PyScheduleKitConfigurationError(
            "BusinessCalendar JSON is malformed."
        ) from exc

    if not isinstance(payload, dict):
        raise PyScheduleKitConfigurationError(
            "BusinessCalendar JSON must contain an object."
        )

    return _decode_business_calendar_payload(payload)


def encode_business_calendar_collection(
    calendars: tuple[BusinessCalendar, ...],
) -> str:
    """Serialize a deterministic file-provider calendar collection."""

    ordered = sorted(
        calendars,
        key=lambda calendar: (
            calendar.calendar_ref.value,
            calendar.revision.value,
        ),
    )
    return json.dumps(
        {
            "schema_version": _CALENDAR_COLLECTION_CODEC_VERSION,
            "calendars": [
                _encode_business_calendar_payload(calendar)
                for calendar in ordered
            ],
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def decode_business_calendar_collection(value: str) -> tuple[BusinessCalendar, ...]:
    """Decode a strict versioned collection used by FileCalendarProvider."""

    try:
        raw = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise PyScheduleKitConfigurationError(
            "BusinessCalendar collection JSON is malformed."
        ) from exc

    if not isinstance(raw, dict):
        raise PyScheduleKitConfigurationError(
            "BusinessCalendar collection JSON must contain an object."
        )

    payload = cast(dict[str, Any], raw)
    _require_exact_fields(
        payload,
        expected=_COLLECTION_FIELDS,
        subject="BusinessCalendar collection",
    )
    if payload["schema_version"] != _CALENDAR_COLLECTION_CODEC_VERSION:
        raise PyScheduleKitConfigurationError(
            "Unsupported BusinessCalendar collection schema version."
        )

    raw_calendars = payload["calendars"]
    if not isinstance(raw_calendars, list):
        raise PyScheduleKitConfigurationError(
            "BusinessCalendar collection 'calendars' must be a list."
        )

    calendars = tuple(
        _decode_business_calendar_payload(
            _require_object(item, subject="BusinessCalendar collection entry")
        )
        for item in raw_calendars
    )
    keys = [
        (calendar.calendar_ref, calendar.revision)
        for calendar in calendars
    ]
    if len(keys) != len(set(keys)):
        raise PyScheduleKitConfigurationError(
            "BusinessCalendar collection contains duplicate revisions."
        )

    return tuple(
        sorted(
            calendars,
            key=lambda calendar: (
                calendar.calendar_ref.value,
                calendar.revision.value,
            ),
        )
    )


def _encode_business_calendar_payload(
    calendar: BusinessCalendar,
) -> dict[str, object]:
    return {
        "schema_version": _CALENDAR_CODEC_VERSION,
        "reference": calendar.calendar_ref.value,
        "revision": calendar.revision.value,
        "working_weekdays": sorted(calendar.working_weekdays),
        "holidays": sorted(day.isoformat() for day in calendar.holidays),
        "extra_working_days": sorted(
            day.isoformat() for day in calendar.extra_working_days
        ),
    }


def _decode_business_calendar_payload(
    payload: dict[str, Any],
) -> BusinessCalendar:
    _require_exact_fields(
        payload,
        expected=_CALENDAR_FIELDS,
        subject="BusinessCalendar",
    )
    if payload["schema_version"] != _CALENDAR_CODEC_VERSION:
        raise PyScheduleKitConfigurationError(
            "Unsupported BusinessCalendar schema version."
        )

    reference = payload["reference"]
    revision = payload["revision"]
    working_weekdays = payload["working_weekdays"]
    holidays = payload["holidays"]
    extra_working_days = payload["extra_working_days"]

    if not isinstance(reference, str):
        raise PyScheduleKitConfigurationError(
            "BusinessCalendar reference must be a string."
        )
    if not isinstance(revision, int) or isinstance(revision, bool):
        raise PyScheduleKitConfigurationError(
            "BusinessCalendar revision must be an integer."
        )
    if not isinstance(working_weekdays, list) or not all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in working_weekdays
    ):
        raise PyScheduleKitConfigurationError(
            "BusinessCalendar working_weekdays must be a list of integers."
        )

    try:
        return BusinessCalendar(
            calendar_ref=CalendarRef(reference),
            revision=CalendarRevision(revision),
            working_weekdays=frozenset(cast(list[int], working_weekdays)),
            holidays=frozenset(
                _decode_date_list(holidays, field="holidays")
            ),
            extra_working_days=frozenset(
                _decode_date_list(
                    extra_working_days,
                    field="extra_working_days",
                )
            ),
        )
    except ValueError as exc:
        raise PyScheduleKitConfigurationError(
            f"Invalid BusinessCalendar definition: {exc}"
        ) from exc


def _decode_date_list(value: object, *, field: str) -> tuple[date, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        raise PyScheduleKitConfigurationError(
            f"BusinessCalendar {field} must be a list of ISO dates."
        )

    try:
        return tuple(date.fromisoformat(item) for item in cast(list[str], value))
    except ValueError as exc:
        raise PyScheduleKitConfigurationError(
            f"BusinessCalendar {field} contains an invalid ISO date."
        ) from exc


def _require_object(value: object, *, subject: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PyScheduleKitConfigurationError(f"{subject} must be an object.")
    return cast(dict[str, Any], value)


def _require_exact_fields(
    payload: dict[str, Any],
    *,
    expected: frozenset[str],
    subject: str,
) -> None:
    actual = frozenset(payload)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise PyScheduleKitConfigurationError(
            f"{subject} fields do not match the supported schema; "
            f"missing={missing!r}, unknown={unknown!r}."
        )
