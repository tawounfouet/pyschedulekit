"""LOT-04 qualification tests for CronTrigger."""

from datetime import UTC, datetime

import pytest

from pyschedulekit.domain.time import (
    AmbiguousLocalTimeError,
    Instant,
    NonexistentLocalTimeError,
    Timezone,
)
from pyschedulekit.domain.triggers import (
    CronAmbiguousTimePolicy,
    CronNonexistentTimePolicy,
    CronSearchLimitError,
    CronTrigger,
    InvalidCronExpressionError,
)
from pyschedulekit.testing import TriggerContractSuite


def _instant(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
) -> Instant:
    return Instant(datetime(year, month, day, hour, minute, tzinfo=UTC))


def test_t_cron_001_daily_expression_returns_next_strict_occurrence() -> None:
    trigger = CronTrigger("0 9 * * *", timezone=Timezone("UTC"))

    assert trigger.next_after(_instant(2026, 1, 5, 8, 59)) == _instant(
        2026, 1, 5, 9, 0
    )
    assert trigger.next_after(_instant(2026, 1, 5, 9, 0)) == _instant(
        2026, 1, 6, 9, 0
    )


def test_t_cron_002_lists_ranges_and_steps_are_supported() -> None:
    trigger = CronTrigger(
        "*/15 9-10 * 1,2 1-5",
        timezone=Timezone("UTC"),
    )

    assert trigger.next_after(_instant(2026, 1, 5, 9, 7)) == _instant(
        2026, 1, 5, 9, 15
    )
    assert trigger.next_after(_instant(2026, 1, 5, 10, 45)) == _instant(
        2026, 1, 6, 9, 0
    )


def test_t_cron_003_sunday_accepts_zero_and_seven() -> None:
    sunday_zero = CronTrigger("0 9 * * 0", timezone=Timezone("UTC"))
    sunday_seven = CronTrigger("0 9 * * 7", timezone=Timezone("UTC"))
    reference = _instant(2026, 1, 9, 12, 0)

    expected = _instant(2026, 1, 11, 9, 0)

    assert sunday_zero.next_after(reference) == expected
    assert sunday_seven.next_after(reference) == expected


def test_t_cron_004_vixie_day_of_month_and_week_use_or_semantics() -> None:
    trigger = CronTrigger(
        "0 9 13 * 1",
        timezone=Timezone("UTC"),
    )

    assert trigger.next_after(_instant(2026, 1, 6)) == _instant(
        2026, 1, 12, 9, 0
    )


def test_t_cron_005_wildcard_day_of_month_makes_weekday_authoritative() -> None:
    trigger = CronTrigger(
        "0 9 * * 1",
        timezone=Timezone("UTC"),
    )

    assert trigger.next_after(_instant(2026, 1, 6)) == _instant(
        2026, 1, 12, 9, 0
    )


def test_t_cron_006_wildcard_weekday_makes_day_of_month_authoritative() -> None:
    trigger = CronTrigger(
        "0 9 13 * *",
        timezone=Timezone("UTC"),
    )

    assert trigger.next_after(_instant(2026, 1, 6)) == _instant(
        2026, 1, 13, 9, 0
    )


def test_t_cron_007_leap_day_can_be_found_across_multiple_years() -> None:
    trigger = CronTrigger(
        "0 12 29 2 *",
        timezone=Timezone("UTC"),
    )

    assert trigger.next_after(_instant(2026, 3, 1)) == _instant(
        2028, 2, 29, 12, 0
    )


def test_t_cron_008_timezone_changes_absolute_occurrence() -> None:
    trigger = CronTrigger(
        "0 9 * * *",
        timezone=Timezone("Europe/Paris"),
    )

    assert trigger.next_after(_instant(2026, 1, 5, 7, 59)) == _instant(
        2026, 1, 5, 8, 0
    )


def test_t_cron_009_nonexistent_dst_time_is_skipped_by_default() -> None:
    trigger = CronTrigger(
        "30 2 * * *",
        timezone=Timezone("Europe/Paris"),
    )

    assert trigger.next_after(_instant(2026, 3, 28, 2, 0)) == _instant(
        2026, 3, 30, 0, 30
    )


def test_t_cron_010_nonexistent_dst_time_can_raise_explicitly() -> None:
    trigger = CronTrigger(
        "30 2 * * *",
        timezone=Timezone("Europe/Paris"),
        nonexistent_time=CronNonexistentTimePolicy.RAISE,
    )

    with pytest.raises(NonexistentLocalTimeError):
        trigger.next_after(_instant(2026, 3, 28, 2, 0))


def test_t_cron_011_ambiguous_dst_time_uses_first_fold_by_default() -> None:
    trigger = CronTrigger(
        "30 2 * * *",
        timezone=Timezone("Europe/Paris"),
    )

    assert trigger.next_after(_instant(2026, 10, 24, 3, 0)) == _instant(
        2026, 10, 25, 0, 30
    )


def test_t_cron_012_ambiguous_dst_time_can_choose_second_fold() -> None:
    trigger = CronTrigger(
        "30 2 * * *",
        timezone=Timezone("Europe/Paris"),
        ambiguous_time=CronAmbiguousTimePolicy.SECOND,
    )

    assert trigger.next_after(_instant(2026, 10, 24, 3, 0)) == _instant(
        2026, 10, 25, 1, 30
    )


def test_t_cron_013_ambiguous_dst_time_can_raise_explicitly() -> None:
    trigger = CronTrigger(
        "30 2 * * *",
        timezone=Timezone("Europe/Paris"),
        ambiguous_time=CronAmbiguousTimePolicy.RAISE,
    )

    with pytest.raises(AmbiguousLocalTimeError):
        trigger.next_after(_instant(2026, 10, 24, 3, 0))


@pytest.mark.parametrize(
    "expression",
    [
        "* * * *",
        "* * * * * *",
        "60 * * * *",
        "* 24 * * *",
        "* * 0 * *",
        "* * * 13 *",
        "* * * * 8",
        "*/0 * * * *",
        "10-5 * * * *",
        "foo * * * *",
        "1,,2 * * * *",
    ],
)
def test_t_cron_014_invalid_expression_is_rejected(expression: str) -> None:
    with pytest.raises(InvalidCronExpressionError):
        CronTrigger(expression, timezone=Timezone("UTC"))


def test_t_cron_015_impossible_calendar_expression_hits_bounded_search_limit() -> None:
    trigger = CronTrigger(
        "0 0 31 2 *",
        timezone=Timezone("UTC"),
    )

    with pytest.raises(CronSearchLimitError):
        trigger.next_after(_instant(2026, 1, 1))


def test_t_cron_016_trigger_contract_is_deterministic_and_strictly_progressing() -> None:
    trigger = CronTrigger(
        "0,30 9-10 * * 1-5",
        timezone=Timezone("Europe/Paris"),
    )

    TriggerContractSuite.assert_conforms(
        trigger,
        (
            _instant(2026, 1, 5, 7, 0),
            _instant(2026, 1, 5, 8, 0),
            _instant(2026, 1, 5, 8, 30),
        ),
    )
