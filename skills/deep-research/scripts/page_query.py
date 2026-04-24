#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Reopen narrow slices from a markdown or text page artifact."""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path
from typing import Any

from artifact_output import emit_json_result
from contracts import ContractViolationError, precondition

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


def _selector_count(
    heading: str | None,
    start_line: int | None,
    end_line: int | None,
    chunk: int | None,
) -> int:
    return int(bool(heading)) + int(start_line is not None or end_line is not None) + int(chunk is not None)


def _read_lines(file_path: Path) -> list[str]:
    return file_path.read_text(encoding="utf-8", errors="replace").splitlines()


def _heading_sections(lines: list[str]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line_number, line in enumerate(lines, start=1):
        match = _HEADING_RE.match(line)
        if not match:
            continue

        if current is not None:
            current["end_line"] = line_number - 1
            current["content"] = "\n".join(
                lines[current["start_line"] - 1:current["end_line"]]
            )
            sections.append(current)

        current = {
            "heading": match.group(2).strip(),
            "level": len(match.group(1)),
            "start_line": line_number,
        }

    if current is not None:
        current["end_line"] = len(lines)
        current["content"] = "\n".join(
            lines[current["start_line"] - 1:current["end_line"]]
        )
        sections.append(current)

    return sections


@precondition(
    lambda file_path, **_: file_path.exists(),
    "Markdown page not found",
)
@precondition(
    lambda heading, start_line, end_line, chunk, **_: _selector_count(heading, start_line, end_line, chunk) == 1,
    "Provide exactly one of heading, line range, or chunk",
)
@precondition(
    lambda start_line, end_line, **_: (start_line is None and end_line is None) or (start_line is not None and end_line is not None),
    "Line queries require both start_line and end_line",
)
@precondition(
    lambda start_line, end_line, **_: (start_line is None and end_line is None) or (start_line >= 1 and end_line >= start_line),
    "Line queries require positive, ordered line numbers",
)
@precondition(
    lambda chunk, **_: chunk is None or chunk >= 1,
    "Chunk number must be >= 1",
)
@precondition(
    lambda chunk_size, **_: chunk_size >= 1,
    "Chunk size must be >= 1",
)
def query_markdown_page(
    file_path: Path,
    *,
    heading: str | None = None,
    start_line: int | None = None,
    end_line: int | None = None,
    chunk: int | None = None,
    chunk_size: int = 40,
) -> dict[str, Any]:
    """Return a narrow slice from a markdown/text page."""
    lines = _read_lines(file_path)

    if heading is not None:
        normalized = heading.strip().casefold()
        for section in _heading_sections(lines):
            if section["heading"].casefold() == normalized:
                return {
                    "mode": "heading",
                    "path": str(file_path),
                    "heading": section["heading"],
                    "level": section["level"],
                    "start_line": section["start_line"],
                    "end_line": section["end_line"],
                    "line_count": section["end_line"] - section["start_line"] + 1,
                    "content": section["content"],
                }
        raise ContractViolationError(f"Heading not found: {heading}", kind="precondition")

    if start_line is not None and end_line is not None:
        if end_line > len(lines):
            raise ContractViolationError(
                f"Line range {start_line}:{end_line} exceeds file length {len(lines)}",
                kind="precondition",
            )

        selected = lines[start_line - 1:end_line]
        return {
            "mode": "lines",
            "path": str(file_path),
            "start_line": start_line,
            "end_line": end_line,
            "line_count": len(selected),
            "content": "\n".join(selected),
        }

    if chunk is not None:
        chunk_count = max(1, math.ceil(len(lines) / chunk_size))
        if chunk > chunk_count:
            raise ContractViolationError(
                f"Chunk {chunk} exceeds chunk count {chunk_count}",
                kind="precondition",
            )

        start = (chunk - 1) * chunk_size + 1
        end = min(chunk * chunk_size, len(lines))
        selected = lines[start - 1:end]
        return {
            "mode": "chunk",
            "path": str(file_path),
            "chunk": chunk,
            "chunk_size": chunk_size,
            "chunk_count": chunk_count,
            "start_line": start,
            "end_line": end,
            "line_count": len(selected),
            "content": "\n".join(selected),
        }

    raise ContractViolationError("No selector provided", kind="precondition")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Query a markdown/text page and return a narrow slice.")
    parser.add_argument("--file", required=True, type=Path, help="Path to the markdown/text page")
    parser.add_argument("--heading", help="Return the section starting at this heading")
    parser.add_argument("--start-line", type=int, help="Inclusive start line for a line-range slice")
    parser.add_argument("--end-line", type=int, help="Inclusive end line for a line-range slice")
    parser.add_argument("--chunk", type=int, help="1-based chunk number for fixed-size line chunks")
    parser.add_argument("--chunk-size", type=int, default=40, help="Lines per chunk when using --chunk")
    parser.add_argument("--output", "-o", type=Path, help="Write full JSON results to this file and emit a compact artifact envelope on stdout")
    args = parser.parse_args(argv)

    try:
        result = query_markdown_page(
            args.file,
            heading=args.heading,
            start_line=args.start_line,
            end_line=args.end_line,
            chunk=args.chunk,
            chunk_size=args.chunk_size,
        )
    except ContractViolationError as exc:
        sys.exit(f"ERROR: {exc}")

    emit_json_result(result, output_path=args.output, artifact_kind="deep-research-page-query")


if __name__ == "__main__":
    main()