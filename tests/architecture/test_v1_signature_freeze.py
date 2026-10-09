"""V1-01.D executable constructor and method signature freeze."""

from __future__ import annotations

import inspect
from enum import Enum
from typing import Any

from pyschedulekit.api import (
    AnyOfTrigger,
    AsyncPythonTargetRegistry,
    AsyncioExecutor,
    BusinessCalendar,
    BusinessDayTrigger,
    CalendarRef,
    CalendarRevision,
    CalendarSnapshotRef,
    ConcurrencyPolicy,
    CronAmbiguousTimePolicy,
    CronDialect,
    CronNonexistentTimePolicy,
    CronTrigger,
    DateTrigger,
    Duration,
    ExecutorRegistry,
    ExponentialBackoff,
    FileCalendarProvider,
    FixedBackoff,
    GracePeriod,
    HttpExecutor,
    HttpMethod,
    HttpRequestSpec,
    HttpTargetRegistry,
    InMemoryCalendarProvider,
    InMemoryObservationSink,
    Instant,
    IntervalTrigger,
    LocalExecutor,
    MisfirePolicy,
    MisfirePolicyAction,
    NoBackoff,
    PythonTargetRegistry,
    RetentionPolicy,
    RetryPolicy,
    RoutingExecutor,
    Scheduler,
    SqliteCalendarProvider,
    SqliteUnitOfWorkFactory,
    TargetRef,
    Timezone,
)
from pyschedulekit.postgres import PostgresUnitOfWorkFactory
from pyschedulekit.testing import (
    FixedClock,
    MutableClock,
    TriggerContractSuite,
    add_request_with_parent,
)

POK = "POSITIONAL_OR_KEYWORD"
KW = "KEYWORD_ONLY"
VAR = "VAR_POSITIONAL"
REQUIRED = "<required>"
FACTORY = "<factory>"


def _default(value: object) -> object:
    if value is inspect.Parameter.empty:
        return REQUIRED
    if repr(value) == FACTORY:
        return FACTORY
    if isinstance(value, Enum):
        return f"{type(value).__name__}.{value.name}"
    return value


def _shape(callable_object: object) -> tuple[tuple[str, str, object], ...]:
    signature = inspect.signature(callable_object)
    return tuple(
        (name, parameter.kind.name, _default(parameter.default))
        for name, parameter in signature.parameters.items()
    )


CONSTRUCTORS: dict[str, tuple[object, tuple[tuple[str, str, object], ...]]] = {
    "AnyOfTrigger": (AnyOfTrigger, (("triggers", VAR, REQUIRED),)),
    "AsyncPythonTargetRegistry": (AsyncPythonTargetRegistry, ()),
    "AsyncioExecutor": (
        AsyncioExecutor,
        (
            ("registry", KW, REQUIRED),
            ("clock", KW, REQUIRED),
        ),
    ),
    "BusinessCalendar": (
        BusinessCalendar,
        (
            ("calendar_ref", POK, REQUIRED),
            ("revision", POK, FACTORY),
            ("working_weekdays", POK, FACTORY),
            ("holidays", POK, FACTORY),
            ("extra_working_days", POK, FACTORY),
        ),
    ),
    "BusinessDayTrigger": (
        BusinessDayTrigger,
        (
            ("ordinal", POK, 1),
            ("hour", POK, 0),
            ("minute", POK, 0),
            ("ambiguous_time", POK, "CronAmbiguousTimePolicy.FIRST"),
            ("nonexistent_time", POK, "CronNonexistentTimePolicy.SKIP"),
        ),
    ),
    "CalendarRef": (CalendarRef, (("value", POK, REQUIRED),)),
    "CalendarRevision": (CalendarRevision, (("value", POK, 1),)),
    "CalendarSnapshotRef": (
        CalendarSnapshotRef,
        (
            ("calendar_ref", POK, REQUIRED),
            ("revision", POK, REQUIRED),
        ),
    ),
    "ConcurrencyPolicy": (
        ConcurrencyPolicy,
        (
            ("mode", POK, "ConcurrencyMode.ALLOW"),
            ("max_instances", POK, None),
            ("overflow", POK, "ConcurrencyOverflowPolicy.QUEUE"),
        ),
    ),
    "CronTrigger": (
        CronTrigger,
        (
            ("expression", POK, REQUIRED),
            ("timezone", POK, REQUIRED),
            ("dialect", POK, "CronDialect.VIXIE"),
            ("ambiguous_time", POK, "CronAmbiguousTimePolicy.FIRST"),
            ("nonexistent_time", POK, "CronNonexistentTimePolicy.SKIP"),
        ),
    ),
    "DateTrigger": (DateTrigger, (("at", POK, REQUIRED),)),
    "Duration": (Duration, (("value", POK, REQUIRED),)),
    "ExecutorRegistry": (ExecutorRegistry, (("executors", POK, None),)),
    "ExponentialBackoff": (
        ExponentialBackoff,
        (
            ("initial_delay", POK, REQUIRED),
            ("multiplier", POK, 2.0),
            ("max_delay", POK, None),
        ),
    ),
    "FileCalendarProvider": (
        FileCalendarProvider,
        (
            ("path", POK, REQUIRED),
            ("max_bytes", KW, 1_048_576),
        ),
    ),
    "FixedBackoff": (FixedBackoff, (("delay", POK, REQUIRED),)),
    "FixedClock": (FixedClock, (("current", POK, REQUIRED),)),
    "GracePeriod": (GracePeriod, (("duration", POK, REQUIRED),)),
    "HttpExecutor": (
        HttpExecutor,
        (
            ("registry", KW, REQUIRED),
            ("clock", KW, REQUIRED),
        ),
    ),
    "HttpRequestSpec": (
        HttpRequestSpec,
        (
            ("url", POK, REQUIRED),
            ("method", POK, "HttpMethod.POST"),
            ("headers", POK, ()),
            ("body", POK, None),
        ),
    ),
    "HttpTargetRegistry": (HttpTargetRegistry, ()),
    "InMemoryCalendarProvider": (InMemoryCalendarProvider, (("calendars", POK, ()),)),
    "InMemoryObservationSink": (InMemoryObservationSink, ()),
    "Instant": (Instant, (("value", POK, REQUIRED),)),
    "IntervalTrigger": (
        IntervalTrigger,
        (
            ("every", POK, REQUIRED),
            ("anchor", POK, REQUIRED),
        ),
    ),
    "LocalExecutor": (
        LocalExecutor,
        (
            ("registry", KW, REQUIRED),
            ("clock", KW, REQUIRED),
        ),
    ),
    "MisfirePolicy": (
        MisfirePolicy,
        (
            ("action", POK, "MisfirePolicyAction.RUN_NOW"),
            ("grace", POK, FACTORY),
            ("max_occurrences", POK, 100),
        ),
    ),
    "MutableClock": (MutableClock, (("current", POK, REQUIRED),)),
    "NoBackoff": (NoBackoff, ()),
    "PostgresUnitOfWorkFactory": (
        PostgresUnitOfWorkFactory,
        (
            ("dsn", POK, REQUIRED),
            ("connection_provider", KW, None),
            ("connection_releaser", KW, None),
        ),
    ),
    "PythonTargetRegistry": (PythonTargetRegistry, ()),
    "RetentionPolicy": (
        RetentionPolicy,
        (
            ("execution_history", POK, REQUIRED),
            ("published_outbox", POK, REQUIRED),
        ),
    ),
    "RetryPolicy": (
        RetryPolicy,
        (
            ("max_attempts", POK, 1),
            ("backoff", POK, FACTORY),
            ("retryable_categories", POK, FACTORY),
        ),
    ),
    "RoutingExecutor": (RoutingExecutor, (("executors", POK, REQUIRED),)),
    "Scheduler": (
        Scheduler,
        (
            ("clock", KW, None),
            ("uow_factory", KW, None),
            ("calendar_provider", KW, None),
            ("registry", KW, None),
            ("http_registry", KW, None),
            ("executors", KW, None),
            ("executor_registry", KW, None),
            ("worker_id", KW, None),
            ("claim_ttl", KW, None),
            ("lease_heartbeat_interval", KW, None),
            ("admission_lock_ttl", KW, None),
            ("materialization_lease_ttl", KW, None),
            ("observation_sink", KW, None),
        ),
    ),
    "SqliteCalendarProvider": (SqliteCalendarProvider, (("database", POK, REQUIRED),)),
    "SqliteUnitOfWorkFactory": (SqliteUnitOfWorkFactory, (("database", POK, REQUIRED),)),
    "TargetRef": (
        TargetRef,
        (
            ("kind", POK, REQUIRED),
            ("reference", POK, REQUIRED),
        ),
    ),
    "Timezone": (Timezone, (("name", POK, REQUIRED),)),
}


METHODS: dict[str, tuple[object, tuple[tuple[str, str, object], ...]]] = {
    "ConcurrencyPolicy.allow": (ConcurrencyPolicy.allow, ()),
    "ConcurrencyPolicy.limit": (
        ConcurrencyPolicy.limit,
        (
            ("max_instances", KW, REQUIRED),
            ("overflow", KW, "ConcurrencyOverflowPolicy.QUEUE"),
        ),
    ),
    "Duration.days": (Duration.days, (("value", POK, REQUIRED),)),
    "Duration.hours": (Duration.hours, (("value", POK, REQUIRED),)),
    "Duration.minutes": (Duration.minutes, (("value", POK, REQUIRED),)),
    "Duration.seconds": (Duration.seconds, (("value", POK, REQUIRED),)),
    "ExecutorRegistry.register": (
        ExecutorRegistry.register,
        (
            ("self", POK, REQUIRED),
            ("kind", POK, REQUIRED),
            ("executor", POK, REQUIRED),
            ("replace", KW, False),
        ),
    ),
    "ExecutorRegistry.resolve": (
        ExecutorRegistry.resolve,
        (
            ("self", POK, REQUIRED),
            ("kind", POK, REQUIRED),
        ),
    ),
    "FileCalendarProvider.resolve": (
        FileCalendarProvider.resolve,
        (
            ("self", POK, REQUIRED),
            ("reference", POK, REQUIRED),
            ("revision", KW, None),
        ),
    ),
    "GracePeriod.seconds": (GracePeriod.seconds, (("value", POK, REQUIRED),)),
    "GracePeriod.zero": (GracePeriod.zero, ()),
    "InMemoryCalendarProvider.register": (
        InMemoryCalendarProvider.register,
        (
            ("self", POK, REQUIRED),
            ("calendar", POK, REQUIRED),
            ("replace", KW, False),
        ),
    ),
    "InMemoryCalendarProvider.resolve": (
        InMemoryCalendarProvider.resolve,
        (
            ("self", POK, REQUIRED),
            ("reference", POK, REQUIRED),
            ("revision", KW, None),
        ),
    ),
    "Instant.parse": (Instant.parse, (("value", POK, REQUIRED),)),
    "MisfirePolicy.catch_up": (
        MisfirePolicy.catch_up,
        (
            ("grace", KW, None),
            ("max_occurrences", KW, 100),
        ),
    ),
    "MisfirePolicy.coalesce": (
        MisfirePolicy.coalesce,
        (
            ("grace", KW, None),
            ("max_occurrences", KW, 100),
        ),
    ),
    "MisfirePolicy.run_now": (
        MisfirePolicy.run_now,
        (
            ("grace", KW, None),
            ("max_occurrences", KW, 100),
        ),
    ),
    "MisfirePolicy.skip": (
        MisfirePolicy.skip,
        (
            ("grace", KW, None),
            ("max_occurrences", KW, 100),
        ),
    ),
    "MutableClock.advance": (
        MutableClock.advance,
        (
            ("self", POK, REQUIRED),
            ("duration", POK, REQUIRED),
        ),
    ),
    "MutableClock.set": (
        MutableClock.set,
        (
            ("self", POK, REQUIRED),
            ("instant", POK, REQUIRED),
        ),
    ),
    "RetentionPolicy.days": (
        RetentionPolicy.days,
        (
            ("execution_history", KW, REQUIRED),
            ("published_outbox", KW, REQUIRED),
        ),
    ),
    "RetryPolicy.none": (RetryPolicy.none, ()),
    "Scheduler.add_schedule": (
        Scheduler.add_schedule,
        (
            ("self", POK, REQUIRED),
            ("target", KW, REQUIRED),
            ("trigger", KW, REQUIRED),
            ("id", KW, None),
            ("timezone", KW, None),
            ("calendar", KW, None),
            ("misfire", KW, None),
            ("concurrency", KW, None),
            ("retry", KW, None),
            ("timeout", KW, None),
        ),
    ),
    "Scheduler.cancel_execution": (
        Scheduler.cancel_execution,
        (
            ("self", POK, REQUIRED),
            ("execution_id", POK, REQUIRED),
        ),
    ),
    "Scheduler.cancel_schedule": (
        Scheduler.cancel_schedule,
        (
            ("self", POK, REQUIRED),
            ("schedule_id", POK, REQUIRED),
        ),
    ),
    "Scheduler.cleanup": (
        Scheduler.cleanup,
        (
            ("self", POK, REQUIRED),
            ("policy", POK, REQUIRED),
            ("limit", KW, 1000),
        ),
    ),
    "Scheduler.dispatch_outbox": (
        Scheduler.dispatch_outbox,
        (
            ("self", POK, REQUIRED),
            ("publisher", POK, REQUIRED),
            ("limit", KW, 100),
        ),
    ),
    "Scheduler.health": (Scheduler.health, (("self", POK, REQUIRED),)),
    "Scheduler.inspect_execution": (
        Scheduler.inspect_execution,
        (
            ("self", POK, REQUIRED),
            ("execution_id", POK, REQUIRED),
        ),
    ),
    "Scheduler.inspect_schedule": (
        Scheduler.inspect_schedule,
        (
            ("self", POK, REQUIRED),
            ("schedule_id", POK, REQUIRED),
        ),
    ),
    "Scheduler.pause_schedule": (
        Scheduler.pause_schedule,
        (
            ("self", POK, REQUIRED),
            ("schedule_id", POK, REQUIRED),
        ),
    ),
    "Scheduler.readiness": (Scheduler.readiness, (("self", POK, REQUIRED),)),
    "Scheduler.reconcile": (
        Scheduler.reconcile,
        (
            ("self", POK, REQUIRED),
            ("limit", KW, 1000),
        ),
    ),
    "Scheduler.recover": (
        Scheduler.recover,
        (
            ("self", POK, REQUIRED),
            ("limit", KW, 1000),
        ),
    ),
    "Scheduler.register_async_target": (
        Scheduler.register_async_target,
        (
            ("self", POK, REQUIRED),
            ("reference", POK, REQUIRED),
            ("target", POK, REQUIRED),
        ),
    ),
    "Scheduler.register_executor": (
        Scheduler.register_executor,
        (
            ("self", POK, REQUIRED),
            ("target_kind", POK, REQUIRED),
            ("executor", POK, REQUIRED),
        ),
    ),
    "Scheduler.register_http_target": (
        Scheduler.register_http_target,
        (
            ("self", POK, REQUIRED),
            ("reference", POK, REQUIRED),
            ("request", POK, REQUIRED),
        ),
    ),
    "Scheduler.register_target": (
        Scheduler.register_target,
        (
            ("self", POK, REQUIRED),
            ("reference", POK, REQUIRED),
            ("target", POK, REQUIRED),
        ),
    ),
    "Scheduler.resume_schedule": (
        Scheduler.resume_schedule,
        (
            ("self", POK, REQUIRED),
            ("schedule_id", POK, REQUIRED),
        ),
    ),
    "Scheduler.run_forever": (
        Scheduler.run_forever,
        (
            ("self", POK, REQUIRED),
            ("max_sleep", KW, None),
            ("poll_interval", KW, None),
            ("limit", KW, 100),
        ),
    ),
    "Scheduler.run_pending": (
        Scheduler.run_pending,
        (
            ("self", POK, REQUIRED),
            ("limit", KW, 100),
        ),
    ),
    "Scheduler.shutdown": (
        Scheduler.shutdown,
        (
            ("self", POK, REQUIRED),
            ("mode", KW, "ShutdownMode.WAIT"),
            ("timeout", KW, None),
        ),
    ),
    "Scheduler.stop": (Scheduler.stop, (("self", POK, REQUIRED),)),
    "SqliteCalendarProvider.register": (
        SqliteCalendarProvider.register,
        (
            ("self", POK, REQUIRED),
            ("calendar", POK, REQUIRED),
            ("replace", KW, False),
        ),
    ),
    "SqliteCalendarProvider.resolve": (
        SqliteCalendarProvider.resolve,
        (
            ("self", POK, REQUIRED),
            ("reference", POK, REQUIRED),
            ("revision", KW, None),
        ),
    ),
    "TargetRef.async_python": (TargetRef.async_python, (("reference", POK, REQUIRED),)),
    "TargetRef.http": (TargetRef.http, (("reference", POK, REQUIRED),)),
    "TargetRef.python": (TargetRef.python, (("reference", POK, REQUIRED),)),
    "TargetRef.workflow": (TargetRef.workflow, (("reference", POK, REQUIRED),)),
    "TriggerContractSuite.assert_conforms": (
        TriggerContractSuite.assert_conforms,
        (
            ("trigger", POK, REQUIRED),
            ("references", POK, REQUIRED),
        ),
    ),
    "TriggerContractSuite.assert_deterministic": (
        TriggerContractSuite.assert_deterministic,
        (
            ("trigger", POK, REQUIRED),
            ("references", POK, REQUIRED),
        ),
    ),
    "TriggerContractSuite.assert_strict_progression": (
        TriggerContractSuite.assert_strict_progression,
        (
            ("trigger", POK, REQUIRED),
            ("references", POK, REQUIRED),
        ),
    ),
    "add_request_with_parent": (
        add_request_with_parent,
        (
            ("uow", KW, REQUIRED),
            ("request", KW, REQUIRED),
        ),
    ),
}


def test_v1_01d_constructor_signatures_are_frozen() -> None:
    mismatches = {
        name: {"expected": expected, "actual": _shape(callable_object)}
        for name, (callable_object, expected) in CONSTRUCTORS.items()
        if _shape(callable_object) != expected
    }
    assert not mismatches


def test_v1_01d_documented_method_signatures_are_frozen() -> None:
    mismatches = {
        name: {"expected": expected, "actual": _shape(callable_object)}
        for name, (callable_object, expected) in METHODS.items()
        if _shape(callable_object) != expected
    }
    assert not mismatches
