#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml >= 6.0",
# ]
# ///
"""KB search — full-text search across knowledge base files.

Searches all .md files in knowledge/ and sources/ (excluding .kb/) for a
query string.  Returns matching files with context lines, scored by
relevance (hit density).

Supports:
  - Multiple matches per file (default) or first-match-only (--first-only)
    - Category filtering (--category entities, topics, ideas, etc.)
    - Frontmatter filters for idea kind and tags (--kind practical, --tag debugging)
  - Multi-term queries scored by term coverage per file
  - Paragraph-aware context (extends to nearest blank lines)

Output: JSON to stdout.  Errors to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from contracts import ContractViolationError, precondition

# Context lines to include around each match — enough for the LLM
# to understand the surrounding content without reading the full file.
_CONTEXT_LINES = 2  # 2 lines before and after the matching line

# Valid knowledge categories that --category can filter by.
_VALID_CATEGORIES = frozenset({
    "entities", "topics", "ideas", "locations", "timeline",
    "sources", "citations", "controversies", "meta", "assets",
    "questions",
})

_VALID_IDEA_KINDS = frozenset({"conceptual", "practical"})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _paragraph_context(lines: list[str], match_idx: int) -> str:
    """Extract context expanding to nearest blank lines (paragraph-aware).

    Expands up/down from match_idx until a blank line is found, bounded
    by _CONTEXT_LINES minimum and 10 lines maximum in each direction to
    avoid returning an entire file for a single match.
    """
    # 10-line cap per direction keeps output bounded even for
    # long paragraphs — the LLM can always read the full file.
    max_expand = 10

    # Expand upward to blank line
    start = match_idx
    for offset in range(1, max_expand + 1):
        candidate = match_idx - offset
        if candidate < 0:
            start = 0
            break
        if lines[candidate].strip() == "":
            start = candidate + 1
            break
        start = candidate
    else:
        start = max(0, match_idx - max_expand)

    # Expand downward to blank line
    end = match_idx + 1
    for offset in range(1, max_expand + 1):
        candidate = match_idx + offset
        if candidate >= len(lines):
            end = len(lines)
            break
        if lines[candidate].strip() == "":
            end = candidate
            break
        end = candidate + 1
    else:
        end = min(len(lines), match_idx + max_expand + 1)

    return "\n".join(lines[start:end])


def _load_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter from a markdown document when present."""
    if not text.startswith("---\n"):
        return {}

    end_idx = text.find("\n---\n", 4)
    if end_idx == -1:
        return {}

    try:
        frontmatter = yaml.safe_load(text[4:end_idx])
    except yaml.YAMLError:
        return {}

    return frontmatter if isinstance(frontmatter, dict) else {}


def _matches_filters(frontmatter: dict, kind: str | None, tag: str | None) -> bool:
    """Return True when frontmatter satisfies the requested filters."""
    if kind:
        if frontmatter.get("idea-kind") != kind:
            return False

    if tag:
        tags = frontmatter.get("tags", [])
        if isinstance(tags, str):
            normalized_tags = {tags.strip().lower()} if tags.strip() else set()
        elif isinstance(tags, list):
            normalized_tags = {
                str(item).strip().lower()
                for item in tags
                if str(item).strip()
            }
        else:
            normalized_tags = set()

        if tag.lower() not in normalized_tags:
            return False

    return True


def _score_file(hit_count: int, total_lines: int, term_hits: int, total_terms: int) -> float:
    """Score a file's relevance.  Higher = more relevant.

    Considers both hit density (matches / file size) and term coverage
    (how many of the query terms appear).  Term coverage is weighted 2×
    because a file matching 3 of 3 query terms is almost always more
    relevant than one matching 1 term 20 times.
    """
    if total_lines == 0:
        return 0.0
    density = hit_count / total_lines
    coverage = term_hits / total_terms if total_terms > 0 else 1.0
    # 2× weight on coverage because matching more distinct terms matters
    # more than hitting the same term repeatedly.
    return round(density + 2.0 * coverage, 6)


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
    category: str | None = None,
    first_only: bool = False,
    kind: str | None = None,
    tag: str | None = None,
) -> dict:
    """Search all KB .md files for a query string (case-insensitive).

    Args:
        kb_path: Root directory of the KB.
        query: Search string.  Multiple words are searched independently
               (a file matching more words scores higher).
        limit: Maximum number of file results to return.
        category: If set, restrict search to ``knowledge/<category>/`` files.
        first_only: If True, return only the first match per file (legacy).
        kind: If set, restrict results to entries with matching ``idea-kind``.
        tag: If set, restrict results to entries whose frontmatter tags contain it.

    Returns a dict with ``matches`` (list sorted by score descending),
    ``truncated``, and ``total_scanned``.
    """
    root = Path(kb_path)

    if kind is not None and kind not in _VALID_IDEA_KINDS:
        raise ContractViolationError(
            f"kind must be one of: {', '.join(sorted(_VALID_IDEA_KINDS))}",
            kind="precondition",
        )

    # Split query into individual terms for scoring.  Each term is
    # compiled as a separate pattern so "quantum computing" matches
    # files containing "quantum" AND/OR "computing", with higher
    # score when both appear.
    terms = [t.strip() for t in query.split() if t.strip()]
    patterns = [re.compile(re.escape(t), re.IGNORECASE) for t in terms]

    # Also compile a full-phrase pattern for exact-phrase matches
    phrase_pattern = re.compile(re.escape(query), re.IGNORECASE)

    # Collect searchable .md files (knowledge/ + sources/ + index.md + log.md)
    search_files: list[Path] = []

    if category:
        # Filter to a specific knowledge category
        cat_dir = root / "knowledge" / category
        if cat_dir.exists():
            search_files.extend(cat_dir.rglob("*.md"))
    else:
        for d in [root / "knowledge", root / "sources"]:
            if d.exists():
                search_files.extend(d.rglob("*.md"))
        for name in ("index.md", "log.md"):
            f = root / name
            if f.exists():
                search_files.append(f)

    # Per-file: collect matches and compute score
    file_results: list[dict] = []

    for fpath in sorted(search_files):
        try:
            rel = str(fpath.relative_to(root))
        except ValueError:
            continue
        if rel.startswith(".kb"):
            continue

        try:
            text = fpath.read_text(encoding="utf-8")
            lines = text.splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        frontmatter = _load_frontmatter(text)
        if (kind or tag) and not _matches_filters(frontmatter, kind, tag):
            continue

        # Find all matching lines
        hit_lines: list[int] = []
        for i, line in enumerate(lines):
            if any(p.search(line) for p in patterns):
                hit_lines.append(i)
                if first_only:
                    break

        if not hit_lines:
            continue

        # Count how many distinct query terms appear in this file
        term_hits = sum(1 for p in patterns if p.search(text))

        score = _score_file(len(hit_lines), len(lines), term_hits, len(terms))

        # Build match entries with paragraph-aware context
        file_matches: list[dict] = []
        for idx in hit_lines:
            context = _paragraph_context(lines, idx)
            file_matches.append({"line": idx + 1, "context": context})

        file_results.append({
            "file": rel,
            "score": score,
            "hits": len(hit_lines),
            "term_coverage": f"{term_hits}/{len(terms)}",
            "matches": file_matches,
        })

    # Sort by score descending
    file_results.sort(key=lambda r: r["score"], reverse=True)

    truncated = False
    if limit is not None and len(file_results) > limit:
        file_results = file_results[:limit]
        truncated = True

    return {
        "results": file_results,
        "truncated": truncated,
        "total_scanned": len(search_files),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Search a knowledge base.")
    parser.add_argument("--path", required=True, help="Path to KB directory")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--limit", type=int, default=None, help="Max file results")
    parser.add_argument(
        "--category",
        default=None,
        choices=sorted(_VALID_CATEGORIES),
        help="Restrict search to a knowledge category",
    )
    parser.add_argument(
        "--first-only",
        action="store_true",
        help="Return only first match per file",
    )
    parser.add_argument(
        "--kind",
        default=None,
        choices=sorted(_VALID_IDEA_KINDS),
        help="Restrict results to entries with a matching idea-kind",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Restrict results to entries whose frontmatter tags contain this tag",
    )

    args = parser.parse_args(argv)
    result = search_kb(
        args.path,
        args.query,
        limit=args.limit,
        category=args.category,
        first_only=args.first_only,
        kind=args.kind,
        tag=args.tag,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
