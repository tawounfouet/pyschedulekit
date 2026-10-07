"""Durable graph reconciliation across requests, executions, and attempts."""

from __future__ import annotations

from dataclasses import dataclass

from pyschedulekit.domain.execution import (
    AttemptState,
    Execution,
    ExecutionId,
    ExecutionPolicySnapshot,
    ExecutionState,
)
from pyschedulekit.domain.execution_request import (
    ExecutionRequest,
    ExecutionRequestState,
    RequestId,
)
from pyschedulekit.ports.persistence import PersistenceConflictError, UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class ReconciliationIssue:
    """One durable inconsistency that was not repaired automatically."""

    code: str
    message: str
    request_id: RequestId | None = None
    execution_id: ExecutionId | None = None


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """Structured result of one bounded reconciliation pass."""

    repaired_request_ids: tuple[RequestId, ...]
    reconstructed_execution_ids: tuple[ExecutionId, ...]
    issues: tuple[ReconciliationIssue, ...]
    scanned_requests: int
    scanned_executions: int
    scan_truncated: bool

    @property
    def repaired(self) -> int:
        return len(self.repaired_request_ids) + len(self.reconstructed_execution_ids)

    @property
    def complete(self) -> bool:
        return not self.scan_truncated and not self.issues


class ReconciliationIncompleteError(RuntimeError):
    """Raised when durable reconciliation cannot prove a coherent graph."""

    def __init__(self, result: ReconciliationResult) -> None:
        super().__init__(
            "Durable reconciliation did not prove a complete coherent scheduler graph."
        )
        self.result = result


class ReconciliationActiveRuntimeError(RuntimeError):
    """Raised when manual reconciliation is requested while local work is active."""


class ReconciliationService:
    """Detect and repair deterministic durable graph drift."""

    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
    ) -> None:
        self._uow_factory = uow_factory

    def reconcile(self, *, limit: int = 1000) -> ReconciliationResult:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        with self._uow_factory() as uow:
            request_scan = uow.requests.list_for_reconciliation(limit=limit + 1)
            execution_scan = uow.executions.list_for_reconciliation(limit=limit + 1)

        requests = request_scan[:limit]
        executions = execution_scan[:limit]
        scan_truncated = len(request_scan) > limit or len(execution_scan) > limit

        repaired_requests: list[RequestId] = []
        reconstructed_executions: list[ExecutionId] = []
        issues: list[ReconciliationIssue] = []

        for request in requests:
            try:
                outcome = self._reconcile_request(request.id)
            except PersistenceConflictError:
                issues.append(
                    ReconciliationIssue(
                        code="reconciliation.persistence_conflict",
                        message="Request reconciliation conflicted with committed state.",
                        request_id=request.id,
                    )
                )
                continue

            if outcome == "request_dispatched":
                repaired_requests.append(request.id)
            elif isinstance(outcome, ExecutionId):
                reconstructed_executions.append(outcome)
            elif isinstance(outcome, ReconciliationIssue):
                issues.append(outcome)

        for execution in executions:
            issue = self._inspect_execution(execution.id)
            if issue is not None:
                issues.extend(issue)

        return ReconciliationResult(
            repaired_request_ids=tuple(repaired_requests),
            reconstructed_execution_ids=tuple(reconstructed_executions),
            issues=tuple(issues),
            scanned_requests=len(requests),
            scanned_executions=len(executions),
            scan_truncated=scan_truncated,
        )

    def _reconcile_request(
        self,
        request_id: RequestId,
    ) -> str | ExecutionId | ReconciliationIssue | None:
        with self._uow_factory() as uow:
            request = uow.requests.get(request_id)
            if request is None:
                return None

            execution = uow.executions.get_by_request(request.id)

            if request.state is ExecutionRequestState.DISPATCHED:
                if execution is not None:
                    return self._request_execution_issue(request, execution)

                reconstructed = Execution.from_request(
                    request=request,
                    created_at=request.created_at,
                )
                uow.executions.add(reconstructed)
                uow.commit()
                return reconstructed.id

            if execution is None:
                return None

            issue = self._request_execution_issue(request, execution)
            if issue is not None:
                return issue

            if request.state in (
                ExecutionRequestState.PENDING,
                ExecutionRequestState.WAITING_ADMISSION,
            ):
                request.mark_dispatched()
                uow.requests.save(request)
                uow.commit()
                return "request_dispatched"

            if request.state in (
                ExecutionRequestState.DROPPED,
                ExecutionRequestState.CANCELLED,
            ):
                return ReconciliationIssue(
                    code="reconciliation.terminal_request_has_execution",
                    message=(
                        f"{request.state.value} ExecutionRequest unexpectedly "
                        "has a durable Execution."
                    ),
                    request_id=request.id,
                    execution_id=execution.id,
                )

            return None

    @staticmethod
    def _request_execution_issue(
        request: ExecutionRequest,
        execution: Execution,
    ) -> ReconciliationIssue | None:
        if execution.request_id != request.id:
            return ReconciliationIssue(
                code="reconciliation.execution_request_identity_mismatch",
                message="Execution references a different ExecutionRequest identity.",
                request_id=request.id,
                execution_id=execution.id,
            )

        if execution.target != request.target:
            return ReconciliationIssue(
                code="reconciliation.execution_target_mismatch",
                message="Execution target differs from its durable ExecutionRequest target.",
                request_id=request.id,
                execution_id=execution.id,
            )

        expected_policy = ExecutionPolicySnapshot(
            timeout=request.timeout,
            retry=request.retry_policy,
        )
        if execution.policy_snapshot != expected_policy:
            return ReconciliationIssue(
                code="reconciliation.execution_policy_mismatch",
                message="Execution policy snapshot differs from its ExecutionRequest policy.",
                request_id=request.id,
                execution_id=execution.id,
            )

        return None

    def _inspect_execution(
        self,
        execution_id: ExecutionId,
    ) -> list[ReconciliationIssue] | None:
        with self._uow_factory() as uow:
            execution = uow.executions.get(execution_id)
            if execution is None:
                return None
            request = uow.requests.get(execution.request_id)
            attempts = uow.attempts.list_for_execution(execution.id)

        issues: list[ReconciliationIssue] = []

        if request is None:
            issues.append(
                ReconciliationIssue(
                    code="reconciliation.execution_missing_request",
                    message="Execution references an ExecutionRequest that does not exist.",
                    execution_id=execution.id,
                )
            )
            return issues

        request_issue = self._request_execution_issue(request, execution)
        if request_issue is not None:
            issues.append(request_issue)

        expected_numbers = list(range(1, execution.attempt_count + 1))
        actual_numbers = [attempt.number for attempt in attempts]
        if actual_numbers != expected_numbers:
            issues.append(
                ReconciliationIssue(
                    code="reconciliation.attempt_history_mismatch",
                    message=(
                        "Persisted Attempt numbers do not match Execution.attempt_count."
                    ),
                    request_id=request.id,
                    execution_id=execution.id,
                )
            )

        running_attempts = [
            attempt for attempt in attempts if attempt.state is AttemptState.RUNNING
        ]
        if execution.state is ExecutionState.RUNNING:
            if (
                len(running_attempts) != 1
                or execution.active_attempt_number is None
                or running_attempts[0].number != execution.active_attempt_number
            ):
                issues.append(
                    ReconciliationIssue(
                        code="reconciliation.running_attempt_mismatch",
                        message=(
                            "RUNNING Execution does not have exactly one matching RUNNING Attempt."
                        ),
                        request_id=request.id,
                        execution_id=execution.id,
                    )
                )
        elif running_attempts:
            issues.append(
                ReconciliationIssue(
                    code="reconciliation.non_running_execution_has_running_attempt",
                    message="Non-RUNNING Execution still has a RUNNING Attempt.",
                    request_id=request.id,
                    execution_id=execution.id,
                )
            )

        latest = attempts[-1] if attempts else None
        if execution.state is ExecutionState.RETRY_WAIT and (
            latest is None
            or latest.state not in (
                AttemptState.FAILED,
                AttemptState.TIMED_OUT,
            )
        ):
            issues.append(
                ReconciliationIssue(
                    code="reconciliation.retry_wait_history_mismatch",
                    message=(
                        "RETRY_WAIT Execution requires a latest FAILED or TIMED_OUT Attempt."
                    ),
                    request_id=request.id,
                    execution_id=execution.id,
                )
            )

        terminal_mapping = {
            ExecutionState.SUCCESS: AttemptState.SUCCESS,
            ExecutionState.FAILED: AttemptState.FAILED,
            ExecutionState.CANCELLED: AttemptState.CANCELLED,
            ExecutionState.TIMED_OUT: AttemptState.TIMED_OUT,
        }
        expected_terminal = terminal_mapping.get(execution.state)
        if expected_terminal is not None and (
            latest is None or latest.state is not expected_terminal
        ):
            issues.append(
                ReconciliationIssue(
                    code="reconciliation.terminal_history_mismatch",
                    message=(
                        "Terminal Execution state does not match its latest persisted Attempt."
                    ),
                    request_id=request.id,
                    execution_id=execution.id,
                )
            )

        return issues or None
