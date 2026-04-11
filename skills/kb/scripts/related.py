#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""KB related — find existing entries that overlap with given keywords.

Given a set of keywords (comma-separated), scores every knowledge entry
by how many keywords it contains.  Returns top N entries sorted by
overlap count.  Useful during kb:add Phase 5 (cross-reference) to find
entries that may need updating when a new source is added.

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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@precondition(
    lambda kb_path, keywords, **_: len(keywords) > 0,
    "keywords list must be non-empty",
)
def find_related(
    kb_path: str,
    keywords: list[str],
    limit: int = 20,
    category: str | None = None,
) -> dict:
    """Find existing knowledge entries that mention one or more keywords.

    Args:
        kb_path: Root directory of the KB.
        keywords: List of keyword strings to search for.
        limit: Maximum number of results to return.
        category: If set, restrict to ``knowledge/<category>/`` only.

    Returns a dict with ``entries`` (list of matching entries sorted by
    overlap count descending, then alphabetically) and ``total_scanned``.
    Each entry contains: ``file``, ``overlap`` (how many keywords matched),
    ``matched_keywords`` (which specific keywords were found), and
    ``title`` (first ``# heading`` line found, or filename).
    """
    root = Path(kb_path)
    knowledge_dir = root / "knowledge"

    if category:
        scan_dir = knowledge_dir / category
        scan_dirs = [scan_dir] if scan_dir.exists() else []
    else:
        scan_dirs = [knowledge_dir]

    # Compile patterns — each keyword is a case-insensitive literal match
    patterns = [(kw, re.compile(re.escape(kw.strip()), re.IGNORECASE)) for kw in keywords if kw.strip()]

    results: list[dict] = []
    total_scanned = 0

    for scan_dir in scan_dirs:
        for fpath in scan_dir.rglob("*.md"):
            total_scanned += 1
            try:
                text = fpath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            matched: list[str] = []
            for kw, pat in patterns:
                if pat.search(text):
                    matched.append(kw)

            if not matched:
                continue

            # Extract title from first # heading
            title = fpath.stem
            for line in text.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break

            try:
                rel = str(fpath.relative_to(root))
            except ValueError:
                rel = str(fpath)

            results.append({
                "file": rel,
                "title": title,
                "overlap": len(matched),
                "matched_keywords": matched,
            })

    # Sort: most overlapping keywords first, then alphabetically by file
    results.sort(key=lambda r: (-r["overlap"], r["file"]))

    truncated = len(results) > limit
    if truncated:
        results = results[:limit]

    return {
        "entries": results,
        "total_scanned": total_scanned,
        "truncated": truncated,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Find KB entries related to given keywords.",
    )
    parser.add_argument("--kb-path", required=True, help="Path to KB directory")
    parser.add_argument(
        "--keywords",
        required=True,
        help="Comma-separated keywords to search for",
    )
    parser.add_argument("--limit", type=int, default=20, help="Max results (default 20)")
    parser.add_argument("--category", default=None, help="Restrict to a knowledge category")

    args = parser.parse_args(argv)
    kw_list = [k.strip() for k in args.keywords.split(",") if k.strip()]

    if not kw_list:
        print("Error: --keywords must contain at least one non-empty keyword", file=sys.stderr)
        sys.exit(1)

    result = find_related(args.kb_path, kw_list, limit=args.limit, category=args.category)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
