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

    # Timeline gaps — years, months, and days
    # Years: detect missing years between existing year entries.
    # Months: detect missing YYYY-MM between consecutive month entries
    #         that share the same year (or adjacent years).
    # Days: detect missing YYYY-MM-DD between consecutive day entries
    #        that share the same month.
    year_entries = _parse_timeline_entries(knowledge_dir, "years")
    if len(year_entries) >= 2:
        nums = []
        for s in year_entries:
            try:
                nums.append(int(s))
            except ValueError:
                pass
        nums.sort()
        for i in range(len(nums) - 1):
            curr, nxt = nums[i], nums[i + 1]
            if nxt - curr > 1:
                for missing in range(curr + 1, nxt):
                    issues.append({
                        "type": "timeline-gap",
                        "file": "knowledge/timeline/years/",
                        "message": f"Missing year entry: {missing} (gap between {curr} and {nxt})",
                        "details": {"between": [str(curr), str(nxt)], "missing": str(missing)},
                    })

    month_entries = _parse_timeline_entries(knowledge_dir, "months")
    if len(month_entries) >= 2:
        valid_months: list[tuple[int, int]] = []
        for s in month_entries:
            parts = s.split("-")
            if len(parts) == 2:
                try:
                    valid_months.append((int(parts[0]), int(parts[1])))
                except ValueError:
                    pass
        valid_months.sort()
        for i in range(len(valid_months) - 1):
            cy, cm = valid_months[i]
            ny, nm = valid_months[i + 1]
            # Walk forward one month at a time
            ty, tm = cy, cm
            while True:
                tm += 1
                if tm > 12:
                    tm = 1
                    ty += 1
                if (ty, tm) >= (ny, nm):
                    break
                missing_str = f"{ty:04d}-{tm:02d}"
                issues.append({
                    "type": "timeline-gap",
                    "file": "knowledge/timeline/months/",
                    "message": f"Missing month entry: {missing_str} (gap between {cy:04d}-{cm:02d} and {ny:04d}-{nm:02d})",
                    "details": {
                        "between": [f"{cy:04d}-{cm:02d}", f"{ny:04d}-{nm:02d}"],
                        "missing": missing_str,
                    },
                })

    day_entries = _parse_timeline_entries(knowledge_dir, "days")
    if len(day_entries) >= 2:
        from datetime import date, timedelta
        valid_days: list[date] = []
        for s in day_entries:
            parts = s.split("-")
            if len(parts) == 3:
                try:
                    valid_days.append(date(int(parts[0]), int(parts[1]), int(parts[2])))
                except ValueError:
                    pass
        valid_days.sort()
        for i in range(len(valid_days) - 1):
            curr_day = valid_days[i]
            next_day = valid_days[i + 1]
            delta = (next_day - curr_day).days
            if delta > 1:
                for offset in range(1, delta):
                    missing_day = curr_day + timedelta(days=offset)
                    missing_str = missing_day.isoformat()
                    issues.append({
                        "type": "timeline-gap",
                        "file": "knowledge/timeline/days/",
                        "message": f"Missing day entry: {missing_str} (gap between {curr_day.isoformat()} and {next_day.isoformat()})",
                        "details": {
                            "between": [curr_day.isoformat(), next_day.isoformat()],
                            "missing": missing_str,
                        },
                    })

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
