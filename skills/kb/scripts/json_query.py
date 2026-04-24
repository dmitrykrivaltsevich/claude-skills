#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Reopen narrow slices from JSON artifacts."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))
from artifact_output import emit_json_result
from contracts import ContractViolationError, precondition

_TOKEN_RE = re.compile(r"([^\.\[\]]+)|(\[(\d+)\])")


def _parse_where(where: str | None) -> tuple[str, str] | None:
    if where is None:
        return None
    key, value = where.split("=", 1)
    return key.strip(), value.strip()


def _apply_selector(data: Any, selector: str | None) -> Any:
    if not selector:
        return data

    current = data
    for match in _TOKEN_RE.finditer(selector):
        key = match.group(1)
        index = match.group(3)
        if key is not None:
            if not isinstance(current, dict) or key not in current:
                raise ContractViolationError(f"Selector key not found: {key}", kind="precondition")
            current = current[key]
        elif index is not None:
            if not isinstance(current, list):
                raise ContractViolationError("Selector index used on non-list value", kind="precondition")
            current = current[int(index)]
    return current


def _apply_where(data: Any, where: tuple[str, str] | None) -> Any:
    if where is None:
        return data
    if not isinstance(data, list):
        raise ContractViolationError("--where can only be used on a list result", kind="precondition")
    key, value = where
    return [item for item in data if isinstance(item, dict) and str(item.get(key, "")) == value]


def _apply_fields(data: Any, fields: list[str] | None) -> Any:
    if not fields:
        return data
    if isinstance(data, list):
        return [
            {field: item.get(field) for field in fields}
            for item in data
            if isinstance(item, dict)
        ]
    if isinstance(data, dict):
        return {field: data.get(field) for field in fields}
    return data


def _apply_limit(data: Any, limit: int | None) -> Any:
    if limit is None or not isinstance(data, list):
        return data
    return data[:limit]


@precondition(
    lambda file_path, **_: file_path.exists(),
    "JSON artifact not found",
)
@precondition(
    lambda where, **_: where is None or "=" in where,
    "where must use key=value format",
)
@precondition(
    lambda limit, **_: limit is None or limit >= 1,
    "limit must be >= 1",
)
def query_json_artifact(
    file_path: Path,
    *,
    selector: str | None = None,
    where: str | None = None,
    fields: list[str] | None = None,
    limit: int | None = None,
) -> Any:
    """Load a JSON artifact and return only the requested slice."""
    data = json.loads(file_path.read_text(encoding="utf-8"))
    selected = _apply_selector(data, selector)
    filtered = _apply_where(selected, _parse_where(where))
    projected = _apply_fields(filtered, fields)
    return _apply_limit(projected, limit)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Query a JSON artifact and return a narrow slice.")
    parser.add_argument("--file", required=True, type=Path, help="Path to the JSON artifact")
    parser.add_argument("--selector", default="", help="Dot/index selector like results, pending_tasks[0], results[1].file")
    parser.add_argument("--where", help="Filter list results with key=value")
    parser.add_argument("--fields", nargs="*", help="Project dict/list-of-dict results onto these fields")
    parser.add_argument("--limit", type=int, help="Limit list results to the first N items")
    parser.add_argument("--output", "-o", type=Path, help="Write full JSON results to this file and emit a compact artifact envelope on stdout")
    args = parser.parse_args(argv)

    try:
        result = query_json_artifact(
            args.file,
            selector=args.selector,
            where=args.where,
            fields=args.fields,
            limit=args.limit,
        )
    except (ContractViolationError, IndexError, json.JSONDecodeError) as exc:
        sys.exit(f"ERROR: {exc}")

    emit_json_result(result, output_path=args.output, artifact_kind="kb-json-query")


if __name__ == "__main__":
    main()