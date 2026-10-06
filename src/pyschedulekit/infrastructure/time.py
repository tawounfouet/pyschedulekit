"""Production time adapters."""

from __future__ import annotations

from datetime import UTC, datetime

from pyschedulekit.domain.time import Instant


class SystemClock:
    """Clock backed by the host wall clock."""

    def now(self) -> Instant:
        return Instant(datetime.now(UTC))
