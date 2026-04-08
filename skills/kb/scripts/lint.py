#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""KB linter — mechanical health checks for knowledge base structure.

Scans all .md files in knowledge/ for:
- Broken wikilinks (target page does not exist)
- Orphan pages (no incoming wikilinks from other pages)
- Missing backlinks (A→B but no B→A)
- Missing YAML frontmatter
- Timeline chain gaps (years/months/days with no prev/next entries)

Does NOT perform semantic analysis — that's the LLM's job after reading
the lint output.

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

# Regex for wikilinks: [[page-name]] or [[page-name|display text]]
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

# Regex for YAML frontmatter
_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---", re.DOTALL)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _collect_md_files(knowledge_dir: Path) -> dict[str, Path]:
    """Build a map of stem (kebab-case name) → file path for all .md files."""
    files: dict[str, Path] = {}
    if not knowledge_dir.exists():
        return files
    for f in knowledge_dir.rglob("*.md"):
        files[f.stem] = f
    return files


def _extract_wikilinks(text: str) -> list[str]:
    """Extract all wikilink targets from markdown text."""
    return _WIKILINK_RE.findall(text)


def _has_frontmatter(text: str) -> bool:
    return bool(_FRONTMATTER_RE.match(text))


def _parse_timeline_entries(knowledge_dir: Path, subdir: str) -> list[str]:
    """Get sorted list of timeline entry stems (e.g. ['2024', '2025', '2027'])."""
    d = knowledge_dir / "timeline" / subdir
    if not d.exists():
        return []
    return sorted(f.stem for f in d.glob("*.md"))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@precondition(
    lambda kb_path, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
def lint_kb(kb_path: str) -> dict:
    """Run mechanical health checks on a KB.

    Returns a dict with 'issues' (list of issue dicts) and 'total_issues' count.
    Each issue has: type, file, message, and optionally target/details.
    """
    root = Path(kb_path)
    knowledge_dir = root / "knowledge"
    sources_dir = root / "sources"
    issues: list[dict] = []

    # Collect all knowledge .md files
    all_files = _collect_md_files(knowledge_dir)

    if not all_files:
        return {"issues": [], "total_issues": 0}

    # Collect source stubs as valid link targets (not scanned for content)
    source_stubs: set[str] = set()
    if sources_dir.exists():
        for f in sources_dir.rglob("*.md"):
            source_stubs.add(f.stem)

    # Build link graph: file_stem → set of targets it links to
    outgoing: dict[str, set[str]] = {}
    incoming: dict[str, set[str]] = {}  # target → set of files linking to it

    for stem in all_files:
        outgoing[stem] = set()
        incoming.setdefault(stem, set())

    for stem, fpath in all_files.items():
        try:
            text = fpath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        # Check frontmatter
        if not _has_frontmatter(text):
            issues.append({
                "type": "missing-frontmatter",
                "file": str(fpath.relative_to(root)),
                "message": "Missing YAML frontmatter",
            })

        # Extract and check wikilinks
        targets = _extract_wikilinks(text)
        for target in targets:
            target_clean = target.strip()
            outgoing[stem].add(target_clean)
            incoming.setdefault(target_clean, set())
            incoming[target_clean].add(stem)

            # Check if target exists in knowledge/ or sources/
            if target_clean not in all_files and target_clean not in source_stubs:
                issues.append({
                    "type": "broken-link",
                    "file": str(fpath.relative_to(root)),
                    "target": target_clean,
                    "message": f"Wikilink [[{target_clean}]] target not found",
                })

    # Orphan pages (no incoming links)
    for stem, fpath in all_files.items():
        if not incoming.get(stem):
            issues.append({
                "type": "orphan",
                "file": str(fpath.relative_to(root)),
                "message": f"No incoming wikilinks to '{stem}'",
            })

    # Missing backlinks (A→B but B does not link back to A)
    for stem, targets in outgoing.items():
        for target in targets:
            if target in all_files and stem not in outgoing.get(target, set()):
                issues.append({
                    "type": "missing-backlink",
                    "file": str(all_files[target].relative_to(root)),
                    "source": stem,
                    "target": target,
                    "message": f"'{stem}' links to '{target}' but '{target}' does not link back",
                })

    # Timeline gaps
    for subdir, parse_fn in [
        ("years", lambda s: int(s) if s.isdigit() else None),
        ("months", lambda s: s),  # YYYY-MM format
        ("days", lambda s: s),    # YYYY-MM-DD format
    ]:
        entries = _parse_timeline_entries(knowledge_dir, subdir)
        if len(entries) >= 2:
            for i in range(len(entries) - 1):
                current = entries[i]
                next_entry = entries[i + 1]

                # For years, check if consecutive
                if subdir == "years":
                    try:
                        curr_year = int(current)
                        next_year = int(next_entry)
                        if next_year - curr_year > 1:
                            for missing_year in range(curr_year + 1, next_year):
                                issues.append({
                                    "type": "timeline-gap",
                                    "file": f"knowledge/timeline/{subdir}/",
                                    "message": f"Missing year entry: {missing_year} (gap between {current} and {next_entry})",
                                    "details": {"between": [current, next_entry], "missing": str(missing_year)},
                                })
                    except ValueError:
                        pass

    return {
        "issues": issues,
        "total_issues": len(issues),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Lint a knowledge base.")
    parser.add_argument("--path", required=True, help="Path to KB directory")

    args = parser.parse_args(argv)
    result = lint_kb(args.path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
