"""Built-in temporal Trigger implementations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import ClassVar

from pyschedulekit.domain.time import (
    Duration,
    Instant,
    NonexistentLocalTimeError,
    Timezone,
)


class InvalidIntervalTriggerError(ValueError):
    """Raised when an IntervalTrigger has no strictly positive interval."""


class InvalidCronExpressionError(ValueError):
    """Raised when a Cron expression cannot be parsed safely."""


class CronSearchLimitError(RuntimeError):
    """Raised when bounded Cron lookup cannot find a valid future occurrence."""


class CronDialect(StrEnum):
    """Supported Cron day-of-month/day-of-week interpretation."""

    VIXIE = "vixie"


class CronAmbiguousTimePolicy(StrEnum):
    """Policy for a local civil time repeated during a DST fold."""

    FIRST = "first"
    SECOND = "second"
    RAISE = "raise"


class CronNonexistentTimePolicy(StrEnum):
    """Policy for a local civil time skipped during a DST gap."""

    SKIP = "skip"
    RAISE = "raise"


@dataclass(frozen=True, slots=True)
class DateTrigger:
    """Finite Trigger that emits one absolute Instant."""

    at: Instant

    def next_after(self, reference: Instant) -> Instant | None:
        """Return the one occurrence when it is still strictly in the future."""

        return self.at if reference < self.at else None


@dataclass(frozen=True, slots=True)
class IntervalTrigger:
    """Fixed-rate Trigger anchored to one absolute Instant.

    Occurrences are always calculated from the anchor:

        anchor + n * every

    Actual execution time never shifts the recurrence.
    """

    every: Duration
    anchor: Instant

    def __post_init__(self) -> None:
        if self.every.value <= timedelta(0):
            raise InvalidIntervalTriggerError(
                "IntervalTrigger requires a strictly positive interval."
            )

    def next_after(self, reference: Instant) -> Instant:
        """Return the first anchored occurrence strictly after reference."""

        if reference < self.anchor:
            return self.anchor

        elapsed = reference.value - self.anchor.value
        completed_intervals = elapsed // self.every.value
        return self.anchor.add(Duration(self.every.value * (completed_intervals + 1)))


@dataclass(frozen=True, slots=True)
class _CronField:
    values: frozenset[int]
    wildcard: bool


@dataclass(frozen=True, slots=True)
class CronTrigger:
    """Five-field calendar Trigger evaluated in an explicit IANA timezone.

    Syntax:

        minute hour day-of-month month day-of-week

    V1 supports numeric values plus wildcards, lists, ranges, and steps.
    Day-of-week uses 0 or 7 for Sunday. Under the Vixie dialect, when both
    day-of-month and day-of-week are restricted, either field may match.
    """

    expression: str
    timezone: Timezone
    dialect: CronDialect = CronDialect.VIXIE
    ambiguous_time: CronAmbiguousTimePolicy = CronAmbiguousTimePolicy.FIRST
    nonexistent_time: CronNonexistentTimePolicy = CronNonexistentTimePolicy.SKIP
    _minute: _CronField = field(init=False, repr=False, compare=False)
    _hour: _CronField = field(init=False, repr=False, compare=False)
    _day_of_month: _CronField = field(init=False, repr=False, compare=False)
    _month: _CronField = field(init=False, repr=False, compare=False)
    _day_of_week: _CronField = field(init=False, repr=False, compare=False)

    _MAX_SEARCH_DAYS: ClassVar[int] = 366 * 8

    def __post_init__(self) -> None:
        parts = self.expression.split()
        if len(parts) != 5:
            raise InvalidCronExpressionError(
                "CronTrigger requires exactly five fields: "
                "minute hour day-of-month month day-of-week."
            )

        minute, hour, day_of_month, month, day_of_week = parts
        object.__setattr__(self, "_minute", _parse_cron_field(minute, minimum=0, maximum=59))
        object.__setattr__(self, "_hour", _parse_cron_field(hour, minimum=0, maximum=23))
        object.__setattr__(
            self,
            "_day_of_month",
            _parse_cron_field(day_of_month, minimum=1, maximum=31),
        )
        object.__setattr__(self, "_month", _parse_cron_field(month, minimum=1, maximum=12))
        object.__setattr__(
            self,
            "_day_of_week",
            _parse_cron_field(
                day_of_week,
                minimum=0,
                maximum=7,
                normalize=lambda value: 0 if value == 7 else value,
            ),
        )

    def next_after(self, reference: Instant) -> Instant:
        """Return the first matching occurrence strictly after reference.

        Lookup walks calendar dates, not historical minutes, and is bounded to
        eight years.
        """

        local_reference = self.timezone.to_local(reference)
        start_date = local_reference.date()

        for day_offset in range(self._MAX_SEARCH_DAYS + 1):
            candidate_date = start_date + timedelta(days=day_offset)
            if not self._date_matches(candidate_date):
                continue

            for hour in sorted(self._hour.values):
                for minute in sorted(self._minute.values):
                    local_candidate = datetime(
                        candidate_date.year,
                        candidate_date.month,
                        candidate_date.day,
                        hour,
                        minute,
                    )
                    candidate = self._resolve_local_candidate(local_candidate)
                    if candidate is not None and candidate > reference:
                        return candidate

        raise CronSearchLimitError(
            "Cron expression produced no valid occurrence within the bounded search horizon."
        )

    def _date_matches(self, candidate: date) -> bool:
        if candidate.month not in self._month.values:
            return False

        day_of_month_matches = candidate.day in self._day_of_month.values
        cron_weekday = (candidate.weekday() + 1) % 7
        day_of_week_matches = cron_weekday in self._day_of_week.values

        if self._day_of_month.wildcard and self._day_of_week.wildcard:
            return True
        if self._day_of_month.wildcard:
            return day_of_week_matches
        if self._day_of_week.wildcard:
            return day_of_month_matches

        if self.dialect is CronDialect.VIXIE:
            return day_of_month_matches or day_of_week_matches

        raise InvalidCronExpressionError(f"Unsupported Cron dialect: {self.dialect!r}.")

    def _resolve_local_candidate(self, local_candidate: datetime) -> Instant | None:
        if self.ambiguous_time is CronAmbiguousTimePolicy.RAISE:
            fold: int | None = None
        elif self.ambiguous_time is CronAmbiguousTimePolicy.FIRST:
            fold = 0
        else:
            fold = 1

        try:
            return self.timezone.resolve_local(local_candidate, fold=fold)
        except NonexistentLocalTimeError:
            if self.nonexistent_time is CronNonexistentTimePolicy.SKIP:
                return None
            raise


def _parse_cron_field(
    expression: str,
    *,
    minimum: int,
    maximum: int,
    normalize: Callable[[int], int] | None = None,
) -> _CronField:
    if not expression:
        raise InvalidCronExpressionError("Cron field must not be empty.")

    values: set[int] = set()
    for term in expression.split(","):
        values.update(
            _expand_cron_term(
                term,
                minimum=minimum,
                maximum=maximum,
            )
        )

    if normalize is not None:
        values = {normalize(value) for value in values}

    if not values:
        raise InvalidCronExpressionError("Cron field must resolve to at least one value.")

    return _CronField(
        values=frozenset(values),
        wildcard=expression == "*",
    )


def _expand_cron_term(
    term: str,
    *,
    minimum: int,
    maximum: int,
) -> set[int]:
    if not term:
        raise InvalidCronExpressionError("Cron list contains an empty term.")

    base, separator, step_text = term.partition("/")
    step = 1
    if separator:
        try:
            step = int(step_text)
        except ValueError as exc:
            raise InvalidCronExpressionError(f"Invalid Cron step value: {step_text!r}.") from exc
        if step <= 0:
            raise InvalidCronExpressionError("Cron step must be strictly positive.")

    if base == "*":
        start = minimum
        end = maximum
    elif "-" in base:
        start_text, range_separator, end_text = base.partition("-")
        if not range_separator or not start_text or not end_text:
            raise InvalidCronExpressionError(f"Invalid Cron range: {base!r}.")
        start = _parse_cron_integer(start_text, minimum=minimum, maximum=maximum)
        end = _parse_cron_integer(end_text, minimum=minimum, maximum=maximum)
        if start > end:
            raise InvalidCronExpressionError(f"Cron range start must not exceed end: {base!r}.")
    else:
        start = _parse_cron_integer(base, minimum=minimum, maximum=maximum)
        end = maximum if separator else start

    return set(range(start, end + 1, step))


def _parse_cron_integer(value: str, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise InvalidCronExpressionError(f"Cron value must be numeric: {value!r}.") from exc

    if parsed < minimum or parsed > maximum:
        raise InvalidCronExpressionError(
            f"Cron value {parsed} is outside the allowed range {minimum}..{maximum}."
        )

    return parsed
