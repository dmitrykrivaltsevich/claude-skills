#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Load, validate, and merge KB style-pattern configuration.

Configuration precedence is CLI > per-KB > skill default.  Each layer is a
`kb-style-patterns/v1` JSON document, and patterns are merged by `id`.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from contracts import ContractViolationError, precondition

_SCHEMA = "kb-style-patterns/v1"
# Scanning is line by line (lint.py finditer(line)), so flags that only change
# cross-line behaviour would silently do nothing.  Advertise only what works.
_SUPPORTED_FLAGS = {"ignorecase"}
DEFAULT_PATTERN_FILE = Path(__file__).with_name("style_patterns.json")


@dataclass
class StylePattern:
    id: str
    enabled: bool
    regex: str
    note: str
    source: str
    compiled: re.Pattern[str]


def _flag_value(flags: list[str]) -> int:
    value = 0
    for flag in flags:
        if flag == "ignorecase":
            value |= re.IGNORECASE
        else:
            raise ContractViolationError(
                f"Unsupported style-pattern flag: {flag}. Patterns are matched line "
                f"by line, so only 'ignorecase' is supported."
            )
    return value


def _validate_flags(raw_flags: object) -> list[str]:
    if raw_flags is None:
        return ["ignorecase"]
    if not isinstance(raw_flags, list) or not all(isinstance(f, str) for f in raw_flags):
        raise ContractViolationError("style-patterns flags must be a list of strings")
    unsupported = set(raw_flags) - _SUPPORTED_FLAGS
    if unsupported:
        raise ContractViolationError(
            f"Unsupported style-pattern flags: {sorted(unsupported)}. Patterns are "
            f"matched line by line, so only 'ignorecase' is supported."
        )
    return list(raw_flags)


def _validate_patterns(raw_patterns: object) -> list[dict]:
    if not isinstance(raw_patterns, list):
        raise ContractViolationError("style-patterns patterns must be a list")

    seen: set[str] = set()
    normalized: list[dict] = []
    for index, raw in enumerate(raw_patterns):
        if not isinstance(raw, dict):
            raise ContractViolationError(
                f"style-patterns pattern #{index} must be an object"
            )

        pattern_id = raw.get("id")
        if not isinstance(pattern_id, str) or not pattern_id.strip():
            raise ContractViolationError(
                f"style-patterns pattern #{index} is missing a non-empty id"
            )
        if pattern_id in seen:
            raise ContractViolationError(
                f"style-patterns contains duplicate pattern id: {pattern_id}"
            )
        seen.add(pattern_id)

        enabled = raw.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ContractViolationError(
                f"style-patterns pattern '{pattern_id}' enabled must be a boolean"
            )

        regex = raw.get("regex")
        if not isinstance(regex, str) or not regex.strip():
            raise ContractViolationError(
                f"style-patterns pattern '{pattern_id}' is missing a regex"
            )

        note = raw.get("note", "")
        if not isinstance(note, str):
            raise ContractViolationError(
                f"style-patterns pattern '{pattern_id}' note must be a string"
            )

        normalized.append(
            {
                "id": pattern_id,
                "enabled": enabled,
                "regex": regex,
                "note": note,
            }
        )

    return normalized


def validate_pattern_data(data: object) -> dict:
    if not isinstance(data, dict):
        raise ContractViolationError("style-patterns data must be an object")
    if data.get("schema") != _SCHEMA:
        raise ContractViolationError(
            f"style-patterns schema must be {_SCHEMA}"
        )

    flags = _validate_flags(data.get("flags"))
    flags_value = _flag_value(flags)
    patterns = _validate_patterns(data.get("patterns"))

    for pattern in patterns:
        try:
            re.compile(pattern["regex"], flags_value)
        except re.error as exc:
            raise ContractViolationError(
                f"Invalid regex for style pattern '{pattern['id']}': {exc}"
            ) from exc

    return {
        "schema": _SCHEMA,
        "flags": flags,
        "patterns": patterns,
    }


@precondition(
    lambda path, **_: isinstance(path, (str, Path)) and str(path).strip() != "",
    "pattern file path must be non-empty",
)
def load_pattern_file(path: str | Path) -> dict:
    """Load and validate one pattern file."""
    pattern_path = Path(path)
    if not pattern_path.exists():
        raise ContractViolationError(
            f"Style pattern file not found: {pattern_path}"
        )

    try:
        text = pattern_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractViolationError(
            f"Could not read style pattern file {pattern_path}: {exc}"
        ) from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContractViolationError(
            f"Invalid JSON in style pattern file {pattern_path}: {exc}"
        ) from exc

    return validate_pattern_data(data)


def _entry_for(raw: dict, source: str, flags_value: int) -> StylePattern:
    try:
        compiled = re.compile(raw["regex"], flags_value)
    except re.error as exc:
        raise ContractViolationError(
            f"Invalid regex for style pattern '{raw['id']}': {exc}"
        ) from exc
    return StylePattern(
        id=raw["id"],
        enabled=raw["enabled"],
        regex=raw["regex"],
        note=raw["note"],
        source=source,
        compiled=compiled,
    )


def _add_entries(
    merged: dict[str, StylePattern],
    order: list[str],
    data: dict,
    source: str,
) -> None:
    flags_value = _flag_value(data["flags"])
    for raw in data["patterns"]:
        entry = _entry_for(raw, source, flags_value)
        if entry.id not in merged:
            order.append(entry.id)
        merged[entry.id] = entry


@precondition(
    lambda kb_path, cli_patterns, **_: (
        kb_path is None
        or (isinstance(kb_path, (str, Path)) and str(kb_path).strip() != "")
    ) and (
        cli_patterns is None
        or (isinstance(cli_patterns, (str, Path)) and str(cli_patterns).strip() != "")
    ),
    "kb_path and cli_patterns must be non-empty when provided",
)
def effective_pattern_entries(
    kb_path: str | Path | None = None,
    cli_patterns: str | Path | None = None,
) -> list[StylePattern]:
    """Return merged pattern entries, including disabled patterns."""
    merged: dict[str, StylePattern] = {}
    order: list[str] = []

    _add_entries(merged, order, load_pattern_file(DEFAULT_PATTERN_FILE), "default")

    if kb_path is not None:
        per_kb_file = Path(kb_path) / ".kb" / "style-patterns.json"
        if per_kb_file.exists():
            _add_entries(merged, order, load_pattern_file(per_kb_file), "per-kb")

    if cli_patterns is not None:
        _add_entries(merged, order, load_pattern_file(cli_patterns), "cli")

    return [merged[pattern_id] for pattern_id in order]


def effective_patterns(
    kb_path: str | Path | None = None,
    cli_patterns: str | Path | None = None,
) -> list[StylePattern]:
    """Return only merged patterns that are enabled."""
    return [entry for entry in effective_pattern_entries(kb_path, cli_patterns) if entry.enabled]


def disabled_pattern_ids(entries: list[StylePattern]) -> list[str]:
    """Return sorted ids of disabled patterns in a merged entry list."""
    return sorted(entry.id for entry in entries if not entry.enabled)