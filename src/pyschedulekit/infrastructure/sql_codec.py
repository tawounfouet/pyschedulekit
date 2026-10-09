"""Versioned JSON codecs for SQL persistence snapshots."""

from __future__ import annotations

import json
from typing import Any, cast

from pyschedulekit.domain.calendar import (
    CalendarRef,
    CalendarRevision,
    CalendarSnapshotRef,
)
from pyschedulekit.domain.concurrency import (
    ConcurrencyMode,
    ConcurrencyOverflowPolicy,
    ConcurrencyPolicy,
)
from pyschedulekit.domain.execution import (
    AttemptResult,
    AttemptState,
    ExecutionPolicySnapshot,
    ExecutionResult,
    ExecutionState,
    Failure,
    FailureCategory,
)
from pyschedulekit.domain.misfire import MisfirePolicy, MisfirePolicyAction
from pyschedulekit.domain.retry import (
    ExponentialBackoff,
    FixedBackoff,
    NoBackoff,
    RetryBackoff,
    RetryPolicy,
)
from pyschedulekit.domain.schedule import ScheduleDefinition, TargetRef
from pyschedulekit.domain.time import Duration, GracePeriod, Instant, Timezone
from pyschedulekit.domain.trigger import CalendarAwareTrigger, Trigger
from pyschedulekit.domain.triggers import (
    BusinessDayTrigger,
    CronAmbiguousTimePolicy,
    CronDialect,
    CronNonexistentTimePolicy,
    CronTrigger,
    DateTrigger,
    IntervalTrigger,
)

_CODEC_VERSION = 1
_SCHEDULE_DEFINITION_CODEC_VERSION = 2


def _dump_with_version(payload: dict[str, Any], *, version: int) -> str:
    return json.dumps(
        {"version": version, "payload": payload},
        separators=(",", ":"),
        sort_keys=True,
    )


def _dump(payload: dict[str, Any]) -> str:
    return _dump_with_version(payload, version=_CODEC_VERSION)


def _load(value: str) -> dict[str, Any]:
    decoded = cast(dict[str, Any], json.loads(value))
    if decoded.get("version") != _CODEC_VERSION:
        raise ValueError("Unsupported SQL persistence codec version.")
    return cast(dict[str, Any], decoded["payload"])


def encode_schedule_definition(definition: ScheduleDefinition) -> str:
    return _dump_with_version(
        {
            "target": _encode_target(definition.target),
            "trigger": _encode_trigger(definition.trigger),
            "timezone": definition.timezone.name,
            "calendar": _encode_calendar_snapshot_ref(definition.calendar),
            "misfire": _encode_misfire(definition.misfire),
            "concurrency": _encode_concurrency(definition.concurrency),
            "retry": _encode_retry(definition.retry),
            "timeout_seconds": _duration_seconds(definition.timeout),
        },
        version=_SCHEDULE_DEFINITION_CODEC_VERSION,
    )


def decode_schedule_definition(value: str) -> ScheduleDefinition:
    decoded = cast(dict[str, Any], json.loads(value))
    version = decoded.get("version")
    if version not in (1, _SCHEDULE_DEFINITION_CODEC_VERSION):
        raise ValueError("Unsupported Schedule definition codec version.")

    payload = cast(dict[str, Any], decoded["payload"])
    if version == 1 and "calendar" in payload:
        raise ValueError("Schedule definition codec v1 must not contain a calendar binding.")

    return ScheduleDefinition(
        target=_decode_target(cast(dict[str, Any], payload["target"])),
        trigger=_decode_trigger(cast(dict[str, Any], payload["trigger"])),
        timezone=Timezone(cast(str, payload["timezone"])),
        calendar=(
            _decode_calendar_snapshot_ref(payload.get("calendar"))
            if version == _SCHEDULE_DEFINITION_CODEC_VERSION
            else None
        ),
        misfire=_decode_misfire(cast(dict[str, Any], payload["misfire"])),
        concurrency=_decode_concurrency(cast(dict[str, Any], payload["concurrency"])),
        retry=_decode_retry(cast(dict[str, Any], payload["retry"])),
        timeout=_decode_optional_duration(payload.get("timeout_seconds")),
    )


def encode_concurrency_policy(policy: ConcurrencyPolicy) -> str:
    return _dump(_encode_concurrency(policy))


def decode_concurrency_policy(value: str) -> ConcurrencyPolicy:
    return _decode_concurrency(_load(value))


def encode_retry_policy(policy: RetryPolicy) -> str:
    return _dump(_encode_retry(policy))


def decode_retry_policy(value: str) -> RetryPolicy:
    return _decode_retry(_load(value))


def encode_execution_policy_snapshot(snapshot: ExecutionPolicySnapshot) -> str:
    return _dump(
        {
            "timeout_seconds": _duration_seconds(snapshot.timeout),
            "retry": _encode_retry(snapshot.retry),
        }
    )


def decode_execution_policy_snapshot(value: str) -> ExecutionPolicySnapshot:
    payload = _load(value)
    return ExecutionPolicySnapshot(
        timeout=_decode_optional_duration(payload.get("timeout_seconds")),
        retry=_decode_retry(cast(dict[str, Any], payload["retry"])),
    )


def encode_attempt_result(result: AttemptResult | None) -> str | None:
    if result is None:
        return None
    return _dump(
        {
            "state": result.state.value,
            "completed_at": result.completed_at.value.isoformat(),
            "failure": _encode_failure(result.failure),
        }
    )


def decode_attempt_result(value: str | None) -> AttemptResult | None:
    if value is None:
        return None
    payload = _load(value)
    return AttemptResult(
        state=AttemptState(cast(str, payload["state"])),
        completed_at=Instant.parse(cast(str, payload["completed_at"])),
        failure=_decode_failure(payload.get("failure")),
    )


def encode_execution_result(result: ExecutionResult | None) -> str | None:
    if result is None:
        return None
    return _dump(
        {
            "state": result.state.value,
            "completed_at": result.completed_at.value.isoformat(),
            "failure": _encode_failure(result.failure),
        }
    )


def decode_execution_result(value: str | None) -> ExecutionResult | None:
    if value is None:
        return None
    payload = _load(value)
    return ExecutionResult(
        state=ExecutionState(cast(str, payload["state"])),
        completed_at=Instant.parse(cast(str, payload["completed_at"])),
        failure=_decode_failure(payload.get("failure")),
    )


def _encode_calendar_snapshot_ref(
    snapshot: CalendarSnapshotRef | None,
) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "reference": snapshot.calendar_ref.value,
        "revision": snapshot.revision.value,
    }


def _decode_calendar_snapshot_ref(payload: object) -> CalendarSnapshotRef | None:
    if payload is None:
        return None

    value = cast(dict[str, Any], payload)
    return CalendarSnapshotRef(
        calendar_ref=CalendarRef(cast(str, value["reference"])),
        revision=CalendarRevision(cast(int, value["revision"])),
    )


def _encode_target(target: TargetRef) -> dict[str, Any]:
    return {"kind": target.kind, "reference": target.reference}


def _decode_target(payload: dict[str, Any]) -> TargetRef:
    return TargetRef(
        kind=cast(str, payload["kind"]),
        reference=cast(str, payload["reference"]),
    )


def _encode_trigger(trigger: Trigger | CalendarAwareTrigger) -> dict[str, Any]:

    if isinstance(trigger, BusinessDayTrigger):
        return {
            "kind": "business_day",
            "ordinal": trigger.ordinal,
            "hour": trigger.hour,
            "minute": trigger.minute,
            "ambiguous_time": trigger.ambiguous_time.value,
            "nonexistent_time": trigger.nonexistent_time.value,
        }

    if isinstance(trigger, DateTrigger):
        return {
            "kind": "date",
            "at": trigger.at.value.isoformat(),
        }

    if isinstance(trigger, IntervalTrigger):
        return {
            "kind": "interval",
            "every_seconds": trigger.every.total_seconds,
            "anchor": trigger.anchor.value.isoformat(),
        }

    if isinstance(trigger, CronTrigger):
        return {
            "kind": "cron",
            "expression": trigger.expression,
            "timezone": trigger.timezone.name,
            "dialect": trigger.dialect.value,
            "ambiguous_time": trigger.ambiguous_time.value,
            "nonexistent_time": trigger.nonexistent_time.value,
        }

    raise TypeError(f"Unsupported Trigger type for SQL persistence: {type(trigger)!r}.")


def _decode_trigger(payload: dict[str, Any]) -> Trigger | CalendarAwareTrigger:
    kind = cast(str, payload["kind"])
    if kind == "business_day":
        return BusinessDayTrigger(
            ordinal=cast(int, payload["ordinal"]),
            hour=cast(int, payload["hour"]),
            minute=cast(int, payload["minute"]),
            ambiguous_time=CronAmbiguousTimePolicy(cast(str, payload["ambiguous_time"])),
            nonexistent_time=CronNonexistentTimePolicy(
                cast(str, payload["nonexistent_time"])
            ),
        )

    if kind == "date":
        return DateTrigger(at=Instant.parse(cast(str, payload["at"])))

    if kind == "interval":
        return IntervalTrigger(
            every=Duration.seconds(cast(float, payload["every_seconds"])),
            anchor=Instant.parse(cast(str, payload["anchor"])),
        )

    if kind == "cron":
        return CronTrigger(
            expression=cast(str, payload["expression"]),
            timezone=Timezone(cast(str, payload["timezone"])),
            dialect=CronDialect(cast(str, payload["dialect"])),
            ambiguous_time=CronAmbiguousTimePolicy(cast(str, payload["ambiguous_time"])),
            nonexistent_time=CronNonexistentTimePolicy(cast(str, payload["nonexistent_time"])),
        )

    raise ValueError(f"Unsupported persisted Trigger kind: {kind!r}.")


def _encode_misfire(policy: MisfirePolicy) -> dict[str, Any]:
    return {
        "action": policy.action.value,
        "grace_seconds": policy.grace.duration.total_seconds,
        "max_occurrences": policy.max_occurrences,
    }


def _decode_misfire(payload: dict[str, Any]) -> MisfirePolicy:
    return MisfirePolicy(
        action=MisfirePolicyAction(cast(str, payload["action"])),
        grace=GracePeriod(Duration.seconds(cast(float, payload["grace_seconds"]))),
        max_occurrences=cast(int, payload["max_occurrences"]),
    )


def _encode_concurrency(policy: ConcurrencyPolicy) -> dict[str, Any]:
    return {
        "mode": policy.mode.value,
        "max_instances": policy.max_instances,
        "overflow": policy.overflow.value,
    }


def _decode_concurrency(payload: dict[str, Any]) -> ConcurrencyPolicy:
    max_instances = payload.get("max_instances")
    return ConcurrencyPolicy(
        mode=ConcurrencyMode(cast(str, payload["mode"])),
        max_instances=None if max_instances is None else cast(int, max_instances),
        overflow=ConcurrencyOverflowPolicy(cast(str, payload["overflow"])),
    )


def _encode_retry(policy: RetryPolicy) -> dict[str, Any]:
    backoff: dict[str, Any]
    if isinstance(policy.backoff, NoBackoff):
        backoff = {"kind": "none"}
    elif isinstance(policy.backoff, FixedBackoff):
        backoff = {
            "kind": "fixed",
            "delay_seconds": policy.backoff.delay.total_seconds,
        }
    elif isinstance(policy.backoff, ExponentialBackoff):
        backoff = {
            "kind": "exponential",
            "initial_delay_seconds": policy.backoff.initial_delay.total_seconds,
            "multiplier": policy.backoff.multiplier,
            "max_delay_seconds": _duration_seconds(policy.backoff.max_delay),
        }
    else:
        raise TypeError(f"Unsupported retry backoff for SQL persistence: {type(policy.backoff)!r}.")

    return {
        "max_attempts": policy.max_attempts,
        "backoff": backoff,
        "retryable_categories": sorted(policy.retryable_categories),
    }


def _decode_retry(payload: dict[str, Any]) -> RetryPolicy:
    backoff_payload = cast(dict[str, Any], payload["backoff"])
    kind = cast(str, backoff_payload["kind"])

    backoff: RetryBackoff
    if kind == "none":
        backoff = NoBackoff()
    elif kind == "fixed":
        backoff = FixedBackoff(Duration.seconds(cast(float, backoff_payload["delay_seconds"])))
    elif kind == "exponential":
        backoff = ExponentialBackoff(
            initial_delay=Duration.seconds(cast(float, backoff_payload["initial_delay_seconds"])),
            multiplier=cast(float, backoff_payload["multiplier"]),
            max_delay=_decode_optional_duration(backoff_payload.get("max_delay_seconds")),
        )
    else:
        raise ValueError(f"Unsupported persisted retry backoff kind: {kind!r}.")

    return RetryPolicy(
        max_attempts=cast(int, payload["max_attempts"]),
        backoff=backoff,
        retryable_categories=frozenset(cast(list[str], payload["retryable_categories"])),
    )


def _encode_failure(failure: Failure | None) -> dict[str, Any] | None:
    if failure is None:
        return None
    return {
        "category": failure.category.value,
        "code": failure.code,
        "message": failure.message,
        "occurred_at": failure.occurred_at.value.isoformat(),
        "retryable_hint": failure.retryable_hint,
        "details": [list(item) for item in failure.details],
    }


def _decode_failure(value: object) -> Failure | None:
    if value is None:
        return None
    payload = cast(dict[str, Any], value)
    raw_details = cast(list[list[str]], payload["details"])
    return Failure(
        category=FailureCategory(cast(str, payload["category"])),
        code=cast(str, payload["code"]),
        message=cast(str, payload["message"]),
        occurred_at=Instant.parse(cast(str, payload["occurred_at"])),
        retryable_hint=cast(bool | None, payload.get("retryable_hint")),
        details=tuple((item[0], item[1]) for item in raw_details),
    )


def _duration_seconds(value: Duration | None) -> float | None:
    return None if value is None else value.total_seconds


def _decode_optional_duration(value: object) -> Duration | None:
    if value is None:
        return None
    return Duration.seconds(cast(float, value))
