"""Repository-wide integrity checks for local Markdown links."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_AUDIT_SESSIONS = REPO_ROOT / "docs" / "audit"

_FENCED_BLOCK = re.compile(r"(?ms)^(`{3,}|~{3,}).*?^\1\s*$")
_MARKDOWN_LINK = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")


def _markdown_files() -> tuple[Path, ...]:
    files = []
    for path in REPO_ROOT.rglob("*.md"):
        relative = path.relative_to(REPO_ROOT)
        if (
            len(relative.parts) >= 4
            and relative.parts[0] == "docs"
            and relative.parts[1] == "audit"
            and "sessions" in relative.parts
        ):
            continue
        files.append(path)
    return tuple(sorted(files))


def _without_fenced_code(text: str) -> str:
    return _FENCED_BLOCK.sub("", text)


def _local_target(raw_target: str) -> str | None:
    target = raw_target.strip()
    if not target or target.startswith("#"):
        return None

    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()

    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None

    return unquote(parsed.path) or None


def test_all_local_markdown_links_resolve_to_existing_paths() -> None:
    broken: list[str] = []

    for markdown in _markdown_files():
        text = _without_fenced_code(markdown.read_text(encoding="utf-8"))

        for match in _MARKDOWN_LINK.finditer(text):
            raw_target = match.group(1)
            target = _local_target(raw_target)
            if target is None:
                continue

            resolved = (markdown.parent / target).resolve()
            if not resolved.exists():
                source = markdown.relative_to(REPO_ROOT)
                broken.append(f"{source}: {raw_target!r}")

    assert not broken, "Broken local Markdown links:\n" + "\n".join(broken)
