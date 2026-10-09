"""CAL-00 qualification for InMemoryCalendarProvider."""

import sqlite3
from datetime import date

import pytest

from pyschedulekit.domain.calendar import (
    BusinessCalendar,
    CalendarRef,
    CalendarRevision,
    CalendarSnapshotRef,
)
from pyschedulekit.errors import PyScheduleKitConfigurationError
from pyschedulekit.infrastructure.calendar import (
    FileCalendarProvider,
    InMemoryCalendarProvider,
    SqliteCalendarProvider,
)
from pyschedulekit.infrastructure.calendar_codec import (
    encode_business_calendar_collection,
)
from pyschedulekit.ports.calendar import CalendarProvider


def _calendar(name: str, revision: int, *, holiday: date | None = None) -> BusinessCalendar:
    return BusinessCalendar(
        calendar_ref=CalendarRef(name),
        revision=CalendarRevision(revision),
        holidays=frozenset() if holiday is None else frozenset({holiday}),
    )


def _accept_provider(provider: CalendarProvider) -> CalendarProvider:
    return provider


def test_in_memory_calendar_provider_satisfies_provider_shape() -> None:
    provider = InMemoryCalendarProvider()

    assert _accept_provider(provider) is provider


def test_provider_resolves_latest_revision_by_default() -> None:
    provider = InMemoryCalendarProvider(
        [
            _calendar("market", 1),
            _calendar("market", 3),
            _calendar("market", 2),
        ]
    )

    assert provider.resolve(CalendarRef("market")).revision == CalendarRevision(3)


def test_provider_resolves_exact_historical_revision() -> None:
    old_holiday = date(2026, 5, 1)
    revision_one = _calendar("market", 1, holiday=old_holiday)
    revision_two = _calendar("market", 2)
    provider = InMemoryCalendarProvider([revision_one, revision_two])

    resolved = provider.resolve(
        CalendarRef("market"),
        revision=CalendarRevision(1),
    )

    assert resolved is revision_one
    assert not resolved.is_working_day(old_holiday)
    assert provider.resolve(CalendarRef("market")).is_working_day(old_holiday)


def test_unknown_calendar_or_revision_fails_as_static_configuration_error() -> None:
    provider = InMemoryCalendarProvider([_calendar("market", 1)])

    with pytest.raises(PyScheduleKitConfigurationError, match="is not registered"):
        provider.resolve(CalendarRef("unknown"))

    with pytest.raises(PyScheduleKitConfigurationError, match="revision 2"):
        provider.resolve(CalendarRef("market"), revision=CalendarRevision(2))


def test_duplicate_revision_requires_explicit_replace() -> None:
    first = _calendar("market", 1, holiday=date(2026, 5, 1))
    replacement = _calendar("market", 1)
    provider = InMemoryCalendarProvider([first])

    with pytest.raises(PyScheduleKitConfigurationError, match="already registered"):
        provider.register(replacement)

    provider.register(replacement, replace=True)

    assert provider.resolve(CalendarRef("market"), revision=CalendarRevision(1)) is replacement


def test_registered_snapshot_references_are_deterministic() -> None:
    provider = InMemoryCalendarProvider(
        [
            _calendar("z-calendar", 2),
            _calendar("a-calendar", 3),
            _calendar("a-calendar", 1),
        ]
    )

    assert provider.references == (
        CalendarSnapshotRef(CalendarRef("a-calendar"), CalendarRevision(1)),
        CalendarSnapshotRef(CalendarRef("a-calendar"), CalendarRevision(3)),
        CalendarSnapshotRef(CalendarRef("z-calendar"), CalendarRevision(2)),
    )


def test_calendar_providers_are_isolated_instances() -> None:
    first = InMemoryCalendarProvider([_calendar("private", 1)])
    second = InMemoryCalendarProvider()

    assert first.resolve(CalendarRef("private")).revision == CalendarRevision(1)

    with pytest.raises(PyScheduleKitConfigurationError):
        second.resolve(CalendarRef("private"))


def test_file_calendar_provider_satisfies_provider_shape(tmp_path) -> None:
    calendar_file = tmp_path / "calendars.json"
    calendar_file.write_text(
        encode_business_calendar_collection((_calendar("market", 1),)),
        encoding="utf-8",
    )

    provider = FileCalendarProvider(calendar_file)

    assert _accept_provider(provider) is provider
    assert provider.resolve(CalendarRef("market")).revision == CalendarRevision(1)


def test_file_provider_loads_one_immutable_snapshot(tmp_path) -> None:
    calendar_file = tmp_path / "calendars.json"
    calendar_file.write_text(
        encode_business_calendar_collection((_calendar("market", 1),)),
        encoding="utf-8",
    )
    provider = FileCalendarProvider(calendar_file)

    calendar_file.write_text(
        encode_business_calendar_collection((_calendar("market", 2),)),
        encoding="utf-8",
    )

    assert provider.resolve(CalendarRef("market")).revision == CalendarRevision(1)


def test_file_provider_rejects_missing_or_oversized_files(tmp_path) -> None:
    with pytest.raises(PyScheduleKitConfigurationError, match="cannot be read"):
        FileCalendarProvider(tmp_path / "missing.json")

    calendar_file = tmp_path / "oversized.json"
    calendar_file.write_text("{}", encoding="utf-8")

    with pytest.raises(PyScheduleKitConfigurationError, match="size limit"):
        FileCalendarProvider(calendar_file, max_bytes=1)


def test_sqlite_calendar_provider_persists_and_reopens_revisions(tmp_path) -> None:
    database = tmp_path / "calendars.db"
    provider = SqliteCalendarProvider(database)
    provider.register(_calendar("market", 1, holiday=date(2026, 5, 1)))
    provider.register(_calendar("market", 3))
    provider.register(_calendar("market", 2))

    reopened = SqliteCalendarProvider(database)

    assert _accept_provider(reopened) is reopened
    assert reopened.resolve(CalendarRef("market")).revision == CalendarRevision(3)
    assert reopened.resolve(
        CalendarRef("market"),
        revision=CalendarRevision(1),
    ).holidays == frozenset({date(2026, 5, 1)})
    assert reopened.references == (
        CalendarSnapshotRef(CalendarRef("market"), CalendarRevision(1)),
        CalendarSnapshotRef(CalendarRef("market"), CalendarRevision(2)),
        CalendarSnapshotRef(CalendarRef("market"), CalendarRevision(3)),
    )


def test_sqlite_provider_duplicate_revision_requires_explicit_replace(tmp_path) -> None:
    provider = SqliteCalendarProvider(tmp_path / "calendars.db")
    provider.register(_calendar("market", 1, holiday=date(2026, 5, 1)))

    with pytest.raises(PyScheduleKitConfigurationError, match="already registered"):
        provider.register(_calendar("market", 1))

    provider.register(_calendar("market", 1), replace=True)

    assert (
        provider.resolve(
            CalendarRef("market"),
            revision=CalendarRevision(1),
        ).holidays
        == frozenset()
    )


def test_sqlite_provider_unknown_calendar_matches_static_provider_error(tmp_path) -> None:
    provider = SqliteCalendarProvider(tmp_path / "calendars.db")

    with pytest.raises(PyScheduleKitConfigurationError, match="is not registered"):
        provider.resolve(CalendarRef("unknown"))

    provider.register(_calendar("market", 1))
    with pytest.raises(PyScheduleKitConfigurationError, match="revision 2"):
        provider.resolve(CalendarRef("market"), revision=CalendarRevision(2))


def test_sqlite_provider_rejects_in_memory_database() -> None:
    with pytest.raises(PyScheduleKitConfigurationError, match="file-backed"):
        SqliteCalendarProvider(":memory:")


def test_sqlite_provider_rejects_future_schema_version(tmp_path) -> None:
    database = tmp_path / "calendars.db"
    SqliteCalendarProvider(database)

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE pyschedulekit_calendar_schema SET version = 2 WHERE singleton = 1"
        )

    with pytest.raises(PyScheduleKitConfigurationError, match="schema version"):
        SqliteCalendarProvider(database)
