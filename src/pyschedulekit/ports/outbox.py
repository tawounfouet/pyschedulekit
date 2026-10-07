"""External publication port for transactional outbox messages."""

from __future__ import annotations

from typing import Protocol

from pyschedulekit.domain.outbox import OutboxMessage


class OutboxPublisher(Protocol):
    """Publish one message to an external transport.

    Implementations should use OutboxMessage.id as their idempotency key.
    """

    def publish(self, message: OutboxMessage) -> None: ...
