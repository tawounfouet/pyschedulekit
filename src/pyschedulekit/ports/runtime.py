"""Runtime waiting contracts."""

from __future__ import annotations

from threading import Event
from typing import Protocol

from pyschedulekit.domain.time import Duration


class LoopWaiter(Protocol):
    """Interruptible waiting strategy between continuous scheduler cycles."""

    def wait(self, *, duration: Duration, stop_event: Event) -> bool:
        """Wait until duration elapses or stop_event is set.

        Return True when the stop signal interrupted the wait.
        """
        ...
