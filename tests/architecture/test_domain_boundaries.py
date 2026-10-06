"""Architecture fitness tests for the pure domain boundary."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOMAIN_ROOT = PROJECT_ROOT / "src" / "pyschedulekit" / "domain"

FORBIDDEN_DOMAIN_IMPORT_PREFIXES = (
    "pyschedulekit.application",
    "pyschedulekit.infrastructure",
    "pyschedulekit.ports",
    "pyschedulekit.runtime",
    "pyschedulekit.api",
)

FORBIDDEN_AMBIENT_CALLS = {
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("date", "today"),
    ("time", "sleep"),
    ("os", "getenv"),
}


def _python_files() -> list[Path]:
    return sorted(DOMAIN_ROOT.rglob("*.py"))


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_modules(tree: ast.Module) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
    return modules


def _qualified_call_name(node: ast.Call) -> tuple[str, str] | None:
    func = node.func
    if not isinstance(func, ast.Attribute):
        return None
    if not isinstance(func.value, ast.Name):
        return None
    return func.value.id, func.attr


def test_domain_does_not_depend_on_outer_layers() -> None:
    violations: list[str] = []

    for path in _python_files():
        tree = _parse(path)
        for module in _imported_modules(tree):
            if module.startswith(FORBIDDEN_DOMAIN_IMPORT_PREFIXES):
                relative_path = path.relative_to(PROJECT_ROOT)
                violations.append(f"{relative_path}: forbidden import {module!r}")

    assert violations == [], "\n".join(violations)


def test_domain_has_no_ambient_time_sleep_or_environment_access() -> None:
    violations: list[str] = []

    for path in _python_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            qualified_name = _qualified_call_name(node)
            if qualified_name is None or qualified_name not in FORBIDDEN_AMBIENT_CALLS:
                continue
            relative_path = path.relative_to(PROJECT_ROOT)
            call_name = ".".join(qualified_name)
            violations.append(
                f"{relative_path}:{node.lineno}: forbidden ambient call {call_name}()"
            )

    assert violations == [], "\n".join(violations)
