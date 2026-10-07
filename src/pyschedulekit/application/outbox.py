"""Transactional outbox production helpers and publication dispatcher."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.domain.outbox import OutboxMessage, OutboxMessageId, OutboxState
from pyschedulekit.domain.time import Instant
from pyschedulekit.ports.outbox import OutboxPublisher
from pyschedulekit.ports.persistence import PersistenceConflictError, UnitOfWorkFactory
from pyschedulekit.ports.time import Clock


def make_outbox_message(
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    created_at: Instant,
    payload: dict[str, str],
    sequence: int = 0,
) -> OutboxMessage:
    """Create one deterministic outbox message from a lifecycle fact."""

    return OutboxMessage.create(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=tuple(payload.items()),
        created_at=created_at,
        sequence=sequence,
    )


@dataclass(frozen=True, slots=True)
class OutboxPublishError:
    message_id: OutboxMessageId
    event_type: str
    message: str


@dataclass(frozen=True, slots=True)
class OutboxDispatchResult:
    published_message_ids: tuple[OutboxMessageId, ...]
    failed_message_ids: tuple[OutboxMessageId, ...]
    errors: tuple[OutboxPublishError, ...]

    @property
    def published(self) -> int:
        return len(self.published_message_ids)

    @property
    def failed(self) -> int:
        return len(self.failed_message_ids)


class OutboxDispatcher:
    """Publish committed outbox messages with at-least-once semantics."""

    def __init__(
        self,
        *,
        clock: Clock,
        uow_factory: UnitOfWorkFactory,
        publisher: OutboxPublisher,
    ) -> None:
        self._clock = clock
        self._uow_factory = uow_factory
        self._publisher = publisher

    def dispatch_pending(self, *, limit: int = 100) -> OutboxDispatchResult:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        with self._uow_factory() as uow:
            pending = uow.outbox.list_pending(limit=limit)

        published: list[OutboxMessageId] = []
        failed: list[OutboxMessageId] = []
        errors: list[OutboxPublishError] = []

        for snapshot in pending:
            try:
                self._publisher.publish(snapshot)
            except Exception as exc:
                error_message = f"{type(exc).__name__}: {exc}"
                try:
                    self._record_failure(
                        message_id=snapshot.id,
                        error=error_message,
                    )
                except PersistenceConflictError:
                    error_message = f"{error_message}; persistence conflict while recording failure"
                failed.append(snapshot.id)
                errors.append(
                    OutboxPublishError(
                        message_id=snapshot.id,
                        event_type=snapshot.event_type,
                        message=error_message,
                    )
                )
                continue

            try:
                marked = self._mark_published(
                    message_id=snapshot.id,
                    published_at=self._clock.now(),
                )
            except PersistenceConflictError as exc:
                failed.append(snapshot.id)
                errors.append(
                    OutboxPublishError(
                        message_id=snapshot.id,
                        event_type=snapshot.event_type,
                        message=(
                            "Message was externally published but local acknowledgement "
                            f"conflicted: {type(exc).__name__}: {exc}"
                        ),
                    )
                )
                continue

            if marked:
                published.append(snapshot.id)

        return OutboxDispatchResult(
            published_message_ids=tuple(published),
            failed_message_ids=tuple(failed),
            errors=tuple(errors),
        )

    def _mark_published(
        self,
        *,
        message_id: OutboxMessageId,
        published_at: Instant,
    ) -> bool:
        with self._uow_factory() as uow:
            message = uow.outbox.get(message_id)
            if message is None or message.state is OutboxState.PUBLISHED:
                return False

            message.mark_published(published_at=published_at)
            uow.outbox.save(message)
            uow.commit()
            return True

    def _record_failure(
        self,
        *,
        message_id: OutboxMessageId,
        error: str,
    ) -> None:
        with self._uow_factory() as uow:
            message = uow.outbox.get(message_id)
            if message is None or message.state is OutboxState.PUBLISHED:
                return

            message.record_failure(error=error)
            uow.outbox.save(message)
            uow.commit()
