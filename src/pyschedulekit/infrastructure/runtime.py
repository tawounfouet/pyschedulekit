"""Production runtime waiting adapters."""

from __future__ import annotations

from threading import Event

from pyschedulekit.domain.time import Duration


class EventLoopWaiter:
    """Wait using Event.wait() so stop requests interrupt polling promptly."""

    def wait(self, *, duration: Duration, wake_event: Event) -> bool:
        if duration.total_seconds <= 0:
            raise ValueError("Loop wait duration must be greater than zero.")
        return wake_event.wait(duration.total_seconds)
