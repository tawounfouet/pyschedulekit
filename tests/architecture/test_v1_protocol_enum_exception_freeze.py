"""V1-01.E executable Protocol, Enum and exception contract freeze."""

from __future__ import annotations

import inspect
from enum import Enum

from pyschedulekit.api import (
    CalendarProvider,
    CancellationToken,
    Clock,
    ConcurrencyDecisionAction,
    ConcurrencyMode,
    ConcurrencyOverflowPolicy,
    CrashRecoveryActiveRuntimeError,
    CrashRecoveryError,
    CrashRecoveryIncompleteError,
    CronAmbiguousTimePolicy,
    CronDialect,
    CronNonexistentTimePolicy,
    ExecutionCancelledError,
    ExecutionNotFoundError,
    ExecutionState,
    Executor,
    FailureCategory,
    HttpMethod,
    MisfirePolicyAction,
    ObservationSink,
    OutboxPublisher,
    OutboxPublishError,
    OutboxState,
    PreparedTarget,
    PyScheduleKitConfigurationError,
    PyScheduleKitDeprecationWarning,
    PyScheduleKitError,
    PyScheduleKitNotFoundError,
    PyScheduleKitStateError,
    PyScheduleKitTargetError,
    ReconciliationActiveRuntimeError,
    ReconciliationIncompleteError,
    RetryDecisionReason,
    RunPendingError,
    RuntimeAlreadyRunningError,
    ScheduleNotFoundError,
    ScheduleState,
    ShutdownMode,
    TargetResolutionError,
    Trigger,
    UnitOfWorkFactory,
    UnsupportedTargetError,
)
from pyschedulekit.postgres import TransientPersistenceError
from pyschedulekit.testing import TriggerContractViolation

POK = "POSITIONAL_OR_KEYWORD"
KW = "KEYWORD_ONLY"
REQUIRED = "<required>"


def _shape(callable_object: object) -> tuple[tuple[str, str, object], ...]:
    return tuple(
        (
            name,
            parameter.kind.name,
            REQUIRED if parameter.default is inspect.Parameter.empty else parameter.default,
        )
        for name, parameter in inspect.signature(callable_object).parameters.items()
    )


PROTOCOL_METHODS: dict[str, tuple[object, tuple[tuple[str, str, object], ...]]] = {
    "CalendarProvider.resolve": (
        CalendarProvider.resolve,
        (
            ("self", POK, REQUIRED),
            ("reference", POK, REQUIRED),
            ("revision", KW, None),
        ),
    ),
    "CancellationToken.raise_if_cancelled": (
        CancellationToken.raise_if_cancelled,
        (("self", POK, REQUIRED),),
    ),
    "Clock.now": (Clock.now, (("self", POK, REQUIRED),)),
    "Executor.execute": (
        Executor.execute,
        (
            ("self", POK, REQUIRED),
            ("prepared", POK, REQUIRED),
            ("timeout", KW, None),
            ("cancellation_token", KW, None),
            ("fencing_token", KW, None),
            ("idempotency_key", KW, None),
        ),
    ),
    "Executor.prepare": (
        Executor.prepare,
        (
            ("self", POK, REQUIRED),
            ("target", POK, REQUIRED),
        ),
    ),
    "ObservationSink.record": (
        ObservationSink.record,
        (
            ("self", POK, REQUIRED),
            ("observation", POK, REQUIRED),
        ),
    ),
    "OutboxPublisher.publish": (
        OutboxPublisher.publish,
        (
            ("self", POK, REQUIRED),
            ("message", POK, REQUIRED),
        ),
    ),
    "Trigger.next_after": (
        Trigger.next_after,
        (
            ("self", POK, REQUIRED),
            ("reference", POK, REQUIRED),
        ),
    ),
    "UnitOfWorkFactory.__call__": (
        UnitOfWorkFactory.__call__,
        (("self", POK, REQUIRED),),
    ),
}


PROTOCOL_PROPERTIES = {
    "CancellationToken": ("is_cancelled",),
    "PreparedTarget": ("target",),
}


ENUM_VALUES: dict[type[Enum], tuple[tuple[str, object], ...]] = {
    ConcurrencyDecisionAction: (
        ("ADMIT", "admit"),
        ("QUEUE", "queue"),
        ("DROP", "drop"),
    ),
    ConcurrencyMode: (
        ("ALLOW", "allow"),
        ("LIMIT", "limit"),
    ),
    ConcurrencyOverflowPolicy: (
        ("QUEUE", "queue"),
        ("DROP", "drop"),
    ),
    CronAmbiguousTimePolicy: (
        ("FIRST", "first"),
        ("SECOND", "second"),
        ("RAISE", "raise"),
    ),
    CronDialect: (("VIXIE", "vixie"),),
    CronNonexistentTimePolicy: (
        ("SKIP", "skip"),
        ("RAISE", "raise"),
    ),
    ExecutionState: (
        ("QUEUED", "queued"),
        ("RUNNING", "running"),
        ("RETRY_WAIT", "retry_wait"),
        ("SUCCESS", "success"),
        ("FAILED", "failed"),
        ("CANCELLED", "cancelled"),
        ("TIMED_OUT", "timed_out"),
    ),
    FailureCategory: (
        ("TRANSIENT", "transient"),
        ("PERMANENT", "permanent"),
        ("TIMEOUT", "timeout"),
        ("CANCELLED", "cancelled"),
        ("UNKNOWN", "unknown"),
    ),
    HttpMethod: (
        ("GET", "GET"),
        ("POST", "POST"),
        ("PUT", "PUT"),
        ("PATCH", "PATCH"),
        ("DELETE", "DELETE"),
        ("HEAD", "HEAD"),
    ),
    MisfirePolicyAction: (
        ("SKIP", "skip"),
        ("RUN_NOW", "run_now"),
        ("CATCH_UP", "catch_up"),
        ("COALESCE", "coalesce"),
    ),
    OutboxState: (
        ("PENDING", "pending"),
        ("PUBLISHED", "published"),
    ),
    RetryDecisionReason: (
        ("RETRYABLE_FAILURE", "retryable_failure"),
        ("NON_RETRYABLE_FAILURE", "non_retryable_failure"),
        ("ATTEMPTS_EXHAUSTED", "attempts_exhausted"),
    ),
    ScheduleState: (
        ("ACTIVE", "active"),
        ("PAUSED", "paused"),
        ("CANCELLED", "cancelled"),
        ("COMPLETED", "completed"),
    ),
    ShutdownMode: (
        ("WAIT", "wait"),
        ("CANCEL", "cancel"),
    ),
}


EXCEPTION_CATEGORIES: dict[type[BaseException], tuple[type[BaseException], ...]] = {
    CrashRecoveryActiveRuntimeError: (PyScheduleKitStateError, RuntimeError),
    CrashRecoveryIncompleteError: (PyScheduleKitStateError, RuntimeError),
    ExecutionCancelledError: (RuntimeError,),
    ExecutionNotFoundError: (PyScheduleKitNotFoundError, LookupError),
    PyScheduleKitConfigurationError: (PyScheduleKitError, ValueError),
    PyScheduleKitError: (Exception,),
    PyScheduleKitNotFoundError: (PyScheduleKitError, LookupError),
    PyScheduleKitStateError: (PyScheduleKitError, RuntimeError),
    PyScheduleKitTargetError: (PyScheduleKitError, RuntimeError),
    ReconciliationActiveRuntimeError: (PyScheduleKitStateError, RuntimeError),
    ReconciliationIncompleteError: (PyScheduleKitStateError, RuntimeError),
    RuntimeAlreadyRunningError: (PyScheduleKitStateError, RuntimeError),
    ScheduleNotFoundError: (PyScheduleKitNotFoundError, LookupError),
    TargetResolutionError: (PyScheduleKitTargetError, RuntimeError),
    TransientPersistenceError: (RuntimeError,),
    TriggerContractViolation: (AssertionError,),
    UnsupportedTargetError: (TargetResolutionError, PyScheduleKitTargetError, RuntimeError),
}


DIAGNOSTIC_RECORDS_WITH_ERROR_NAMES = (
    CrashRecoveryError,
    OutboxPublishError,
    RunPendingError,
)


def test_v1_01e_protocol_method_shapes_are_frozen() -> None:
    mismatches = {
        name: {"expected": expected, "actual": _shape(member)}
        for name, (member, expected) in PROTOCOL_METHODS.items()
        if _shape(member) != expected
    }
    assert not mismatches


def test_v1_01e_protocol_property_members_are_frozen() -> None:
    for protocol_name, property_names in PROTOCOL_PROPERTIES.items():
        protocol = {
            "CancellationToken": CancellationToken,
            "PreparedTarget": PreparedTarget,
        }[protocol_name]
        for property_name in property_names:
            assert isinstance(protocol.__dict__[property_name], property)


def test_v1_01e_enum_names_values_and_order_are_frozen() -> None:
    actual = {
        enum_type.__name__: tuple((member.name, member.value) for member in enum_type)
        for enum_type in ENUM_VALUES
    }
    expected = {
        enum_type.__name__: members for enum_type, members in ENUM_VALUES.items()
    }
    assert actual == expected


def test_v1_01e_public_exception_categories_are_frozen() -> None:
    missing = {
        exception_type.__name__: tuple(base.__name__ for base in expected_bases)
        for exception_type, expected_bases in EXCEPTION_CATEGORIES.items()
        if not all(issubclass(exception_type, base) for base in expected_bases)
    }
    assert not missing


def test_v1_01e_deprecation_warning_category_is_frozen() -> None:
    assert issubclass(PyScheduleKitDeprecationWarning, DeprecationWarning)
    assert not issubclass(PyScheduleKitDeprecationWarning, PyScheduleKitError)


def test_v1_01e_error_named_diagnostic_records_remain_non_exceptions() -> None:
    assert all(
        not issubclass(record_type, BaseException)
        for record_type in DIAGNOSTIC_RECORDS_WITH_ERROR_NAMES
    )
