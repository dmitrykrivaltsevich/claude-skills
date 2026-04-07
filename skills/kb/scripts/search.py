#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""KB search — full-text grep across knowledge base files.

Searches all .md files in knowledge/ and sources/ (excluding .kb/) for a
query string.  Returns matching files with context lines.

Output: JSON to stdout.  Errors to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from contracts import ContractViolationError, precondition

# Context lines to include around each match — enough for the LLM
# to understand the surrounding content without reading the full file.
_CONTEXT_LINES = 2  # 2 lines before and after the matching line


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@precondition(
    lambda kb_path, query, **_: len(query.strip()) > 0,
    "query must be non-empty",
)
def search_kb(
    kb_path: str,
    query: str,
    limit: int | None = None,
) -> dict:
    """Search all KB .md files for a query string (case-insensitive).

    Returns matches with file path, line number, and context lines.
    Excludes .kb/ internal files.
    """
    root = Path(kb_path)
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    matches: list[dict] = []

    # Collect searchable .md files (knowledge/ + sources/ + index.md + log.md)
    search_dirs = [root / "knowledge", root / "sources"]
    search_files: list[Path] = []

    for d in search_dirs:
        if d.exists():
            search_files.extend(d.rglob("*.md"))

    # Also search top-level index.md and log.md
    for name in ("index.md", "log.md"):
        f = root / name
        if f.exists():
            search_files.append(f)

    for fpath in sorted(search_files):
        # Skip .kb/ directory
        try:
            rel = str(fpath.relative_to(root))
        except ValueError:
            continue
        if rel.startswith(".kb"):
            continue

        try:
            lines = fpath.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        for i, line in enumerate(lines):
            if pattern.search(line):
                # Build context
                start = max(0, i - _CONTEXT_LINES)
                end = min(len(lines), i + _CONTEXT_LINES + 1)
                context = "\n".join(lines[start:end])

                matches.append({
                    "file": rel,
                    "line": i + 1,
                    "context": context,
                })

                if limit is not None and len(matches) >= limit:
                    return {"matches": matches, "truncated": True, "total_scanned": len(search_files)}

                # Skip to next file after first match in this file
                # to avoid flooding with multiple hits from same file
                break

    return {"matches": matches, "truncated": False, "total_scanned": len(search_files)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Search a knowledge base.")
    parser.add_argument("--path", required=True, help="Path to KB directory")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--limit", type=int, default=None, help="Max results")

    args = parser.parse_args(argv)
    result = search_kb(args.path, args.query, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
