"""Tests for the production system clock adapter."""

from datetime import UTC

from pyschedulekit.infrastructure.time import SystemClock


def test_system_clock_returns_utc_instant() -> None:
    instant = SystemClock().now()

    assert instant.value.tzinfo is UTC
