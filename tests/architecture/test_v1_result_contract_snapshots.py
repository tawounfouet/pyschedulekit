"""V1-01.G executable field snapshots for stable public result objects."""

from dataclasses import fields

import pyschedulekit.api as api
from pyschedulekit.api._manifest import V1_PUBLIC_RESULT_TYPES


EXPECTED_FIELDS = {
    "AdmissionSnapshot": (
        "request_id",
        "action",
        "decision",
        "execution_id",
        "reused",
        "lock_denied",
    ),
    "CleanupResult": (
        "evaluated_at",
        "execution_cutoff",
        "outbox_cutoff",
        "execution_graphs_deleted",
        "orphan_requests_deleted",
        "published_outbox_messages_deleted",
    ),
    "ConcurrencyDecision": (
        "action",
        "active_instances",
        "max_instances",
    ),
    "CrashRecoveryError": (
        "execution_id",
        "code",
        "message",
    ),
    "CrashRecoveryResult": (
        "recovered_execution_ids",
        "retried_execution_ids",
        "failed_execution_ids",
        "cancelled_execution_ids",
        "skipped_execution_ids",
        "errors",
        "remaining_running_execution_ids",
        "protected_execution_ids",
    ),
    "ExecutionPolicySnapshot": (
        "timeout",
        "retry",
    ),
    "ExecutionRunSnapshot": (
        "execution",
        "attempt_id",
        "outcome",
        "retry_decision",
    ),
    "ExecutionSnapshot": (
        "execution_id",
        "request_id",
        "state",
        "created_at",
        "attempt_count",
        "active_attempt_number",
        "next_attempt_at",
        "cancellation_requested_at",
        "is_terminal",
        "target_kind",
        "target_reference",
        "failure_category",
        "failure_code",
        "completed_at",
        "policy_snapshot",
    ),
    "ExecutorOutcome": ("failure",),
    "Failure": (
        "category",
        "code",
        "message",
        "occurred_at",
        "retryable_hint",
        "details",
    ),
    "OutboxDispatchResult": (
        "published_message_ids",
        "failed_message_ids",
        "errors",
    ),
    "OutboxPublishError": (
        "message_id",
        "event_type",
        "message",
    ),
    "ReconciliationIssue": (
        "code",
        "message",
        "request_id",
        "execution_id",
    ),
    "ReconciliationResult": (
        "repaired_request_ids",
        "reconstructed_execution_ids",
        "issues",
        "scanned_requests",
        "scanned_executions",
        "scan_truncated",
    ),
    "RetryDecision": (
        "should_retry",
        "reason",
        "next_attempt_number",
        "delay",
    ),
    "RunPendingError": (
        "request_id",
        "code",
        "message",
    ),
    "RunPendingResult": (
        "evaluation_now",
        "materialized_request_ids",
        "executions",
        "schedule_conflicts",
        "unsupported_policy_schedules",
        "recovery_limit_schedules",
        "admissions",
        "errors",
        "claim_denied_execution_ids",
        "materialization_denied_schedule_ids",
    ),
    "ScheduleSnapshot": (
        "schedule_id",
        "state",
        "revision",
        "persistence_version",
        "next_run_time",
        "target_kind",
        "target_reference",
        "timezone",
        "calendar",
        "timeout_seconds",
    ),
    "SchedulerHealth": (
        "healthy",
        "worker_id",
        "persistence_available",
        "runtime_running",
        "shutdown_requested",
        "active_execution_count",
        "cycles_completed",
    ),
    "SchedulerReadiness": (
        "ready",
        "persistence_available",
        "recovered",
        "reconciled",
        "shutdown_requested",
    ),
    "ShutdownResult": (
        "mode",
        "completed",
        "timed_out",
        "active_execution_ids",
    ),
}

EXPECTED_PROPERTIES = {
    "CleanupResult": ("total_deleted",),
    "ConcurrencyDecision": ("admitted",),
    "CrashRecoveryResult": (
        "cancelled",
        "complete",
        "failed",
        "recovered",
        "retried",
    ),
    "ExecutionSnapshot": (
        "cancellation_requested",
        "id",
    ),
    "ExecutorOutcome": ("succeeded",),
    "OutboxDispatchResult": (
        "failed",
        "published",
    ),
    "ReconciliationResult": (
        "complete",
        "repaired",
    ),
    "RunPendingResult": (
        "admission_lock_denied_request_ids",
        "dropped_request_ids",
        "failed",
        "queued_request_ids",
        "retry_scheduled",
        "succeeded",
    ),
}


def _field_names(type_name: str) -> tuple[str, ...]:
    result_type = getattr(api, type_name)
    return tuple(field.name for field in fields(result_type))


def _property_names(type_name: str) -> tuple[str, ...]:
    result_type = getattr(api, type_name)
    return tuple(
        sorted(
            name
            for name, member in vars(result_type).items()
            if isinstance(member, property) and not name.startswith("_")
        )
    )


def test_v1_01g_result_type_inventory_is_exact() -> None:
    assert V1_PUBLIC_RESULT_TYPES == tuple(sorted(EXPECTED_FIELDS))


def test_v1_01g_public_result_fields_are_frozen() -> None:
    mismatches = {
        type_name: {
            "expected": expected,
            "actual": _field_names(type_name),
        }
        for type_name, expected in EXPECTED_FIELDS.items()
        if _field_names(type_name) != expected
    }
    assert not mismatches, f"public result field drift: {mismatches}"


def test_v1_01g_public_result_properties_are_frozen() -> None:
    mismatches = {
        type_name: {
            "expected": expected,
            "actual": _property_names(type_name),
        }
        for type_name, expected in EXPECTED_PROPERTIES.items()
        if _property_names(type_name) != expected
    }
    assert not mismatches, f"public result property drift: {mismatches}"


def test_v1_01g_result_types_are_public_api_exports() -> None:
    missing = [
        type_name
        for type_name in V1_PUBLIC_RESULT_TYPES
        if not hasattr(api, type_name) or type_name not in api.__all__
    ]
    assert not missing, f"result contract types missing from public API: {missing}"
