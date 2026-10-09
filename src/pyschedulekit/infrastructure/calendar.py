"""In-memory BusinessCalendar provider."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path
from threading import RLock

from pyschedulekit.domain.calendar import (
    BusinessCalendar,
    CalendarRef,
    CalendarRevision,
    CalendarSnapshotRef,
)
from pyschedulekit.errors import PyScheduleKitConfigurationError
from pyschedulekit.infrastructure.calendar_codec import (
    decode_business_calendar,
    decode_business_calendar_collection,
    encode_business_calendar,
)


class InMemoryCalendarProvider:
    """Thread-safe process-local provider with explicit versioned registrations."""

    def __init__(self, calendars: Iterable[BusinessCalendar] = ()) -> None:
        self._lock = RLock()
        self._calendars: dict[tuple[CalendarRef, CalendarRevision], BusinessCalendar] = {}

        for calendar in calendars:
            self.register(calendar)

    def register(
        self,
        calendar: BusinessCalendar,
        *,
        replace: bool = False,
    ) -> None:
        """Register one exact calendar revision."""

        key = (calendar.calendar_ref, calendar.revision)
        with self._lock:
            if key in self._calendars and not replace:
                raise PyScheduleKitConfigurationError(
                    "BusinessCalendar revision is already registered: "
                    f"{calendar.calendar_ref.value!r} revision {calendar.revision.value}."
                )
            self._calendars[key] = calendar

    def resolve(
        self,
        reference: CalendarRef,
        *,
        revision: CalendarRevision | None = None,
    ) -> BusinessCalendar:
        """Resolve the latest or requested exact revision."""

        with self._lock:
            if revision is not None:
                calendar = self._calendars.get((reference, revision))
                if calendar is None:
                    raise PyScheduleKitConfigurationError(
                        "BusinessCalendar revision is not registered: "
                        f"{reference.value!r} revision {revision.value}."
                    )
                return calendar

            candidates = [
                calendar
                for (calendar_ref, _), calendar in self._calendars.items()
                if calendar_ref == reference
            ]

        if not candidates:
            raise PyScheduleKitConfigurationError(
                f"BusinessCalendar {reference.value!r} is not registered."
            )

        return max(candidates, key=lambda calendar: calendar.revision)

    @property
    def references(self) -> tuple[CalendarSnapshotRef, ...]:
        """Return a deterministic snapshot of every registered revision."""

        with self._lock:
            return tuple(sorted(calendar.snapshot_ref for calendar in self._calendars.values()))



class FileCalendarProvider:
    """Read-only provider backed by one explicit versioned JSON snapshot file.

    The file is loaded once at construction. Replacing the file on disk does not mutate the
    effective provider; callers create a new provider explicitly when they want to adopt a
    new snapshot.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        max_bytes: int = 1_048_576,
    ) -> None:
        if max_bytes < 1:
            raise PyScheduleKitConfigurationError(
                "FileCalendarProvider max_bytes must be greater than zero."
            )

        self._path = Path(path)
        try:
            payload = self._path.read_bytes()
        except OSError as exc:
            raise PyScheduleKitConfigurationError(
                f"Calendar file cannot be read: {self._path}."
            ) from exc

        if len(payload) > max_bytes:
            raise PyScheduleKitConfigurationError(
                "Calendar file exceeds the configured size limit."
            )

        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PyScheduleKitConfigurationError(
                "Calendar file must be UTF-8 encoded."
            ) from exc

        self._delegate = InMemoryCalendarProvider(
            decode_business_calendar_collection(text)
        )

    def resolve(
        self,
        reference: CalendarRef,
        *,
        revision: CalendarRevision | None = None,
    ) -> BusinessCalendar:
        """Resolve from the immutable file snapshot loaded at construction."""

        return self._delegate.resolve(reference, revision=revision)

    @property
    def references(self) -> tuple[CalendarSnapshotRef, ...]:
        return self._delegate.references

    @property
    def path(self) -> Path:
        return self._path


class SqliteCalendarProvider:
    """Versioned BusinessCalendar provider backed by an isolated SQLite store."""

    _SCHEMA_VERSION = 1

    def __init__(self, database: str | Path) -> None:
        self._database = str(database)
        if self._database == ":memory:":
            raise PyScheduleKitConfigurationError(
                "SqliteCalendarProvider requires a file-backed database."
            )
        self._initialize_schema()

    def register(
        self,
        calendar: BusinessCalendar,
        *,
        replace: bool = False,
    ) -> None:
        """Persist one exact revision explicitly."""

        definition_json = encode_business_calendar(calendar)
        try:
            with self._connect() as connection:
                if replace:
                    connection.execute(
                        """
                        INSERT INTO pyschedulekit_business_calendars(
                            reference, revision, definition_json
                        )
                        VALUES (?, ?, ?)
                        ON CONFLICT(reference, revision)
                        DO UPDATE SET definition_json = excluded.definition_json
                        """,
                        (
                            calendar.calendar_ref.value,
                            calendar.revision.value,
                            definition_json,
                        ),
                    )
                else:
                    connection.execute(
                        """
                        INSERT INTO pyschedulekit_business_calendars(
                            reference, revision, definition_json
                        )
                        VALUES (?, ?, ?)
                        """,
                        (
                            calendar.calendar_ref.value,
                            calendar.revision.value,
                            definition_json,
                        ),
                    )
        except sqlite3.IntegrityError as exc:
            raise PyScheduleKitConfigurationError(
                "BusinessCalendar revision is already registered: "
                f"{calendar.calendar_ref.value!r} revision "
                f"{calendar.revision.value}."
            ) from exc
        except sqlite3.Error as exc:
            raise RuntimeError("SQLite calendar provider write failed.") from exc

    def resolve(
        self,
        reference: CalendarRef,
        *,
        revision: CalendarRevision | None = None,
    ) -> BusinessCalendar:
        """Resolve the latest or requested exact persisted revision."""

        try:
            with self._connect() as connection:
                if revision is None:
                    row = connection.execute(
                        """
                        SELECT revision, definition_json
                        FROM pyschedulekit_business_calendars
                        WHERE reference = ?
                        ORDER BY revision DESC
                        LIMIT 1
                        """,
                        (reference.value,),
                    ).fetchone()
                else:
                    row = connection.execute(
                        """
                        SELECT revision, definition_json
                        FROM pyschedulekit_business_calendars
                        WHERE reference = ? AND revision = ?
                        """,
                        (reference.value, revision.value),
                    ).fetchone()
        except sqlite3.Error as exc:
            raise RuntimeError("SQLite calendar provider read failed.") from exc

        if row is None:
            if revision is None:
                raise PyScheduleKitConfigurationError(
                    f"BusinessCalendar {reference.value!r} is not registered."
                )
            raise PyScheduleKitConfigurationError(
                "BusinessCalendar revision is not registered: "
                f"{reference.value!r} revision {revision.value}."
            )

        persisted_revision = CalendarRevision(int(row[0]))
        calendar = decode_business_calendar(str(row[1]))
        if (
            calendar.calendar_ref != reference
            or calendar.revision != persisted_revision
        ):
            raise PyScheduleKitConfigurationError(
                "Persisted BusinessCalendar identity does not match its SQLite key."
            )
        return calendar

    @property
    def references(self) -> tuple[CalendarSnapshotRef, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT reference, revision
                    FROM pyschedulekit_business_calendars
                    ORDER BY reference, revision
                    """
                ).fetchall()
        except sqlite3.Error as exc:
            raise RuntimeError("SQLite calendar provider read failed.") from exc

        return tuple(
            CalendarSnapshotRef(
                calendar_ref=CalendarRef(str(reference)),
                revision=CalendarRevision(int(revision)),
            )
            for reference, revision in rows
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_schema(self) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS pyschedulekit_calendar_schema (
                        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                        version INTEGER NOT NULL CHECK(version >= 1)
                    )
                    """
                )
                row = connection.execute(
                    "SELECT version FROM pyschedulekit_calendar_schema WHERE singleton = 1"
                ).fetchone()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO pyschedulekit_calendar_schema(singleton, version)
                        VALUES (1, ?)
                        """,
                        (self._SCHEMA_VERSION,),
                    )
                elif int(row[0]) != self._SCHEMA_VERSION:
                    raise PyScheduleKitConfigurationError(
                        "Unsupported SQLite calendar provider schema version."
                    )

                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS pyschedulekit_business_calendars (
                        reference TEXT NOT NULL
                            CHECK(length(trim(reference)) > 0),
                        revision INTEGER NOT NULL CHECK(revision >= 1),
                        definition_json TEXT NOT NULL,
                        PRIMARY KEY(reference, revision)
                    )
                    """
                )
        except PyScheduleKitConfigurationError:
            raise
        except sqlite3.Error as exc:
            raise RuntimeError(
                "SQLite calendar provider schema initialization failed."
            ) from exc
