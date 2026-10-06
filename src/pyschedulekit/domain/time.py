"""Pure temporal value objects used by the scheduling domain."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class InvalidInstantError(ValueError):
    """Raised when an Instant is built from a timezone-naive datetime."""


class InvalidDurationError(ValueError):
    """Raised when a duration is negative."""


class InvalidTimezoneError(ValueError):
    """Raised when an IANA timezone cannot be resolved."""


class InvalidTimeWindowError(ValueError):
    """Raised when a time window is empty or reversed."""


class AmbiguousLocalTimeError(ValueError):
    """Raised when a local civil time maps to two distinct instants."""


class NonexistentLocalTimeError(ValueError):
    """Raised when a local civil time falls inside a DST gap."""


@dataclass(frozen=True, slots=True, order=True)
class Instant:
    """An absolute point on the timeline, normalized to UTC."""

    value: datetime

    def __post_init__(self) -> None:
        if self.value.tzinfo is None or self.value.utcoffset() is None:
            raise InvalidInstantError("Instant requires a timezone-aware datetime.")

        object.__setattr__(self, "value", self.value.astimezone(UTC))

    @classmethod
    def parse(cls, value: str) -> Instant:
        """Parse an ISO-8601 datetime into an Instant."""

        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        return cls(datetime.fromisoformat(normalized))

    def add(self, duration: Duration) -> Instant:
        """Return a new Instant after the supplied elapsed duration."""

        return Instant(self.value + duration.value)

    def elapsed_since(self, earlier: Instant) -> Duration:
        """Return elapsed time since an earlier Instant."""

        delta = self.value - earlier.value
        if delta < timedelta(0):
            raise InvalidDurationError("Earlier instant must not be after this instant.")
        return Duration(delta)


@dataclass(frozen=True, slots=True, order=True)
class Duration:
    """A non-negative elapsed duration."""

    value: timedelta

    def __post_init__(self) -> None:
        if self.value < timedelta(0):
            raise InvalidDurationError("Duration must be greater than or equal to zero.")

    @classmethod
    def seconds(cls, value: int | float) -> Duration:
        return cls(timedelta(seconds=value))

    @classmethod
    def minutes(cls, value: int | float) -> Duration:
        return cls(timedelta(minutes=value))

    @classmethod
    def hours(cls, value: int | float) -> Duration:
        return cls(timedelta(hours=value))

    @classmethod
    def days(cls, value: int | float) -> Duration:
        """Create an elapsed duration where one day means exactly 24 hours."""

        return cls(timedelta(days=value))

    @property
    def total_seconds(self) -> float:
        return self.value.total_seconds()


@dataclass(frozen=True, slots=True)
class Timezone:
    """An IANA timezone with explicit civil-time resolution."""

    name: str
    _zone: ZoneInfo = field(init=False, repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        try:
            zone = ZoneInfo(self.name)
        except ZoneInfoNotFoundError as exc:
            raise InvalidTimezoneError(f"Unknown IANA timezone: {self.name!r}.") from exc

        object.__setattr__(self, "_zone", zone)

    def to_local(self, instant: Instant) -> datetime:
        """Convert an absolute Instant to an aware local datetime."""

        return instant.value.astimezone(self._zone)

    def resolve_local(self, local_datetime: datetime, *, fold: int | None = None) -> Instant:
        """Resolve a naive local civil time into an absolute Instant."""

        if local_datetime.tzinfo is not None:
            raise ValueError("resolve_local() expects a timezone-naive local datetime.")

        if fold not in (None, 0, 1):
            raise ValueError("fold must be None, 0, or 1.")

        candidates = self._valid_candidates(local_datetime)

        if not candidates:
            raise NonexistentLocalTimeError(
                f"{local_datetime.isoformat()} does not exist in timezone {self.name!r}."
            )

        unique_instants = set(candidates.values())
        if len(unique_instants) == 1:
            return next(iter(unique_instants))

        if fold is None:
            raise AmbiguousLocalTimeError(
                f"{local_datetime.isoformat()} is ambiguous in timezone {self.name!r}; "
                "specify fold=0 or fold=1."
            )

        return candidates[fold]

    def _valid_candidates(self, local_datetime: datetime) -> dict[int, Instant]:
        candidates: dict[int, Instant] = {}

        for fold in (0, 1):
            aware = local_datetime.replace(tzinfo=self._zone, fold=fold)
            utc_value = aware.astimezone(UTC)
            round_trip = utc_value.astimezone(self._zone).replace(tzinfo=None)

            if round_trip == local_datetime:
                candidates[fold] = Instant(utc_value)

        return candidates


@dataclass(frozen=True, slots=True)
class TimeWindow:
    """A half-open absolute time window with inclusive start and exclusive end."""

    start: Instant
    end: Instant

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise InvalidTimeWindowError("TimeWindow end must be strictly after start.")

    def contains(self, instant: Instant) -> bool:
        return self.start <= instant < self.end

    @property
    def duration(self) -> Duration:
        return Duration(self.end.value - self.start.value)


@dataclass(frozen=True, slots=True)
class GracePeriod:
    """Maximum non-negative lateness tolerated by a later scheduling policy."""

    duration: Duration

    @classmethod
    def zero(cls) -> GracePeriod:
        return cls(Duration(timedelta(0)))

    @classmethod
    def seconds(cls, value: int | float) -> GracePeriod:
        return cls(Duration.seconds(value))

    def deadline_for(self, scheduled_at: Instant) -> Instant:
        return scheduled_at.add(self.duration)
