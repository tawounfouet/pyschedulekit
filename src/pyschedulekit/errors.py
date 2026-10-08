"""Stable public exception hierarchy for PyScheduleKit."""

from __future__ import annotations


class PyScheduleKitError(Exception):
    """Base class for public PyScheduleKit exceptions."""


class PyScheduleKitConfigurationError(PyScheduleKitError, ValueError):
    """Raised when public configuration is invalid."""


class PyScheduleKitStateError(PyScheduleKitError, RuntimeError):
    """Raised when an operation is incompatible with current scheduler state."""


class PyScheduleKitNotFoundError(PyScheduleKitError, LookupError):
    """Raised when a public identity cannot be resolved."""


class PyScheduleKitTargetError(PyScheduleKitError, RuntimeError):
    """Raised when an execution target cannot be resolved or prepared safely."""


class PyScheduleKitDeprecationWarning(DeprecationWarning):
    """Warning category for compatibility aliases scheduled for removal."""
