"""Retention and cleanup application service."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.application.observability import Observer
from pyschedulekit.domain.time import Duration, Instant
from pyschedulekit.ports.persistence import RetentionCleanupStats, UnitOfWorkFactory
from pyschedulekit.ports.time import Clock


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    """Explicit retention windows for historical scheduler state."""

    execution_history: Duration
    published_outbox: Duration

    @classmethod
    def days(
        cls,
        *,
        execution_history: int | float,
        published_outbox: int | float,
    ) -> RetentionPolicy:
        return cls(
            execution_history=Duration.days(execution_history),
            published_outbox=Duration.days(published_outbox),
        )


@dataclass(frozen=True, slots=True)
class CleanupResult:
    """Structured outcome of one committed retention cleanup."""

    evaluated_at: Instant
    execution_cutoff: Instant
    outbox_cutoff: Instant
    execution_graphs_deleted: int
    orphan_requests_deleted: int
    published_outbox_messages_deleted: int

    @property
    def total_deleted(self) -> int:
        return (
            self.execution_graphs_deleted
            + self.orphan_requests_deleted
            + self.published_outbox_messages_deleted
        )


class RetentionService:
    """Delete only immutable historical state older than explicit cutoffs."""

    def __init__(
        self,
        *,
        clock: Clock,
        uow_factory: UnitOfWorkFactory,
        observer: Observer | None = None,
    ) -> None:
        self._clock = clock
        self._uow_factory = uow_factory
        self._observer = observer or Observer()

    def cleanup(
        self,
        *,
        policy: RetentionPolicy,
        limit: int = 1000,
    ) -> CleanupResult:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        evaluated_at = self._clock.now()
        execution_cutoff = Instant(evaluated_at.value - policy.execution_history.value)
        outbox_cutoff = Instant(evaluated_at.value - policy.published_outbox.value)

        with self._uow_factory() as uow:
            uow.retention.stage_cleanup(
                executions_completed_before=execution_cutoff,
                orphan_requests_created_before=execution_cutoff,
                outbox_published_before=outbox_cutoff,
                limit=limit,
            )
            uow.commit()
            stats = uow.retention.result

        result = self._result(
            evaluated_at=evaluated_at,
            execution_cutoff=execution_cutoff,
            outbox_cutoff=outbox_cutoff,
            stats=stats,
        )
        self._observer.record(
            name="retention.cleanup.completed",
            recorded_at=evaluated_at,
            execution_graphs_deleted=result.execution_graphs_deleted,
            orphan_requests_deleted=result.orphan_requests_deleted,
            published_outbox_messages_deleted=result.published_outbox_messages_deleted,
            total_deleted=result.total_deleted,
        )
        return result

    @staticmethod
    def _result(
        *,
        evaluated_at: Instant,
        execution_cutoff: Instant,
        outbox_cutoff: Instant,
        stats: RetentionCleanupStats,
    ) -> CleanupResult:
        return CleanupResult(
            evaluated_at=evaluated_at,
            execution_cutoff=execution_cutoff,
            outbox_cutoff=outbox_cutoff,
            execution_graphs_deleted=stats.execution_graphs,
            orphan_requests_deleted=stats.orphan_requests,
            published_outbox_messages_deleted=stats.published_outbox_messages,
        )
