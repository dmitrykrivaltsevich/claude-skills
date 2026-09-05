#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""KB linter — mechanical health checks for knowledge base structure.

Two scopes.  Structural checks read knowledge/ only:
- Broken wikilinks (target page does not exist)
- Orphan pages (no incoming wikilinks from other pages)
- Missing backlinks (A→B but no B→A)
- Missing YAML frontmatter
- Timeline chain gaps (years/months/days with no prev/next entries)
- Unreadable files (reported, never fatal, never silent)

Style-phrase scanning covers every .md in the KB except the raw source layer
(sources/files/) and the operation's own bookkeeping (.kb/tasks/,
.kb/rules-proposals.md).

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
from artifact_output import emit_json_result
from contracts import ContractViolationError, precondition
from style_config import disabled_pattern_ids, effective_pattern_entries
from style_review import load_review_records

# Regex for wikilinks: [[page-name]] or [[page-name|display text]]
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

_HEADING_RE = re.compile(r"^ {0,3}#{1,6}(?:\s|$)")
_LIST_ITEM_RE = re.compile(r"^\s{0,3}(?:[-*+]|\d{1,9}[.)])\s")
# Directories the style scan never enters: the raw source layer, and the run
# state kb:lint writes itself (flagging your own bookkeeping is a loop).
_STYLE_EXCLUDED_DIRS = (("sources", "files"), (".kb", "tasks"))
_STYLE_EXCLUDED_FILES = (".kb/rules-proposals.md",)
_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_EXCERPT_MAX_CHARS = 200  # enough context for triage while keeping lint output compact.


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
    # One source of truth with the style scanner: a block the scanner refuses to
    # skip is not frontmatter here either, or its YAML would be linted as prose.
    return _frontmatter_end_line(text) > 0


def _parse_timeline_entries(knowledge_dir: Path, subdir: str) -> list[str]:
    """Get sorted list of timeline entry stems (e.g. ['2024', '2025', '2027'])."""
    d = knowledge_dir / "timeline" / subdir
    if not d.exists():
        return []
    return sorted(f.stem for f in d.glob("*.md"))


def _style_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for path in root.rglob("*.md"):
        relative = path.relative_to(root)
        parts = relative.parts
        if any(parts[: len(excluded)] == excluded for excluded in _STYLE_EXCLUDED_DIRS):
            continue
        if relative.as_posix() in _STYLE_EXCLUDED_FILES:
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def _frontmatter_end_line(text: str) -> int:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return 0
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return index + 1
    return 0


def _code_mask(line: str) -> list[bool]:
    mask = [False] * len(line)
    index = 0
    while index < len(line):
        if line[index] != "`":
            index += 1
            continue
        run = 0
        while index + run < len(line) and line[index + run] == "`":
            run += 1
        delimiter = "`" * run
        close = line.find(delimiter, index + run)
        if close == -1:
            index += 1
            continue
        end = close + run
        for pos in range(index, end):
            mask[pos] = True
        index = end
    return mask


def _quote_mask(line: str) -> list[bool]:
    """Mask spans inside double quotes, so quoted matches get `context: quote`.

    Double quotes only (straight and typographic).  Single quotes are not
    delimiters here: an apostrophe in ordinary prose ("it's", "don't") is
    indistinguishable from an opening quote and would mask arbitrary spans,
    mislabelling prose as quotation.  A phrase in single quotes is therefore
    reported as `prose` — triage it from the excerpt.  Blockquote lines are
    handled separately in `_line_context`.
    """
    mask = [False] * len(line)
    index = 0
    while index < len(line):
        char = line[index]
        if char == '"':
            close = line.find('"', index + 1)
            if close == -1:
                index += 1
                continue
            for pos in range(index, close + 1):
                mask[pos] = True
            index = close + 1
        elif char == "“":
            close = line.find("”", index + 1)
            if close == -1:
                index += 1
                continue
            for pos in range(index, close + 1):
                mask[pos] = True
            index = close + 1
        else:
            index += 1
    return mask


def _closes_fence(match: re.Match[str], line: str, fence_char: str, fence_len: int) -> bool:
    """Whether a fence line closes the open fence.

    CommonMark: the closing fence uses the same character, is at least as long
    as the opening run, and carries no info string.  Checking only the
    character would let a ``` run close a ```` block early, exposing code as
    prose.
    """
    delimiter = match.group(1)
    return (
        delimiter[0] == fence_char
        and len(delimiter) >= fence_len
        and line[match.end():].strip() == ""
    )


def _line_context(line: str, line_no: int, frontmatter_end: int, in_fence: bool) -> str:
    if line_no <= frontmatter_end:
        return "frontmatter"
    if in_fence:
        return "code"
    if _HEADING_RE.match(line):
        return "heading"
    if line.lstrip().startswith(">"):
        return "quote"
    return "prose"


def _indent_width(line: str) -> int:
    width = 0
    for char in line:
        if char == " ":
            width += 1
        elif char == "\t":
            width += 4  # CommonMark counts a tab as four columns.
        else:
            break
    return width


def _excerpt(line: str) -> str:
    text = line.strip()
    if len(text) <= _EXCERPT_MAX_CHARS:
        return text
    return text[:_EXCERPT_MAX_CHARS].rstrip() + "…"


def _scan_style_files(
    root: Path,
    active_patterns: list,
    review_records: dict,
    disabled_ids: list[str],
) -> tuple[list[dict], dict, dict[str, str]]:
    issues: list[dict] = []
    reviewed_findings: list[dict] = []
    unreadable: dict[str, str] = {}
    by_context: dict[str, int] = {}
    by_pattern: dict[str, int] = {}
    by_source: dict[str, int] = {}

    for path in _style_files(root):
        rel_path = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            # One bad file must not abort the lint of every other file; it is
            # reported as an issue so it is neither silent nor fatal.
            unreadable[rel_path] = str(exc)
            continue

        lines = text.splitlines()
        frontmatter_end = _frontmatter_end_line(text)
        in_fence = False
        fence_char = ""
        fence_len = 0
        prev_blank = True
        prev_indented_code = False
        in_list = False

        for line_no, line in enumerate(lines, 1):
            fence = _FENCE_RE.match(line)
            is_indented_code = False
            if in_fence:
                if fence and _closes_fence(fence, line, fence_char, fence_len):
                    in_fence = False
                    fence_char = ""
                    fence_len = 0
                context = "code"
            else:
                if fence:
                    in_fence = True
                    fence_char = fence.group(1)[0]
                    fence_len = len(fence.group(1))
                    context = "code"
                else:
                    context = _line_context(line, line_no, frontmatter_end, in_fence)
                    if context == "prose" and line.strip():
                        indent = _indent_width(line)
                        if _LIST_ITEM_RE.match(line):
                            in_list = True
                        elif indent == 0:
                            in_list = False
                        # An indented code block starts after a blank line and
                        # outside a list; the same indent under a list item, or
                        # straight after text, is continuation prose.
                        if indent >= 4 and not in_list and (prev_blank or prev_indented_code):
                            context = "code"
                            is_indented_code = True

            prev_blank = not line.strip()
            prev_indented_code = is_indented_code

            if context in ("frontmatter", "code"):
                continue

            code_mask = _code_mask(line)
            # Headings carry quotations too, and rule 2 (verbatim-quote) has to
            # reach them wherever they appear.
            quotable = context in ("prose", "heading")
            quote_mask = _quote_mask(line) if quotable else [False] * len(line)

            for pattern in active_patterns:
                for match in pattern.compiled.finditer(line):
                    start, end = match.span()
                    if end <= start:
                        continue
                    if any(code_mask[start:end]):
                        continue

                    match_context = context
                    if quotable and any(quote_mask[start:end]):
                        match_context = "quote"
                    reviewed = (
                        rel_path,
                        line_no,
                        pattern.id,
                        match.group(0),
                    ) in review_records

                    finding = {
                        "type": "style-phrase",
                        "file": rel_path,
                        "line": line_no,
                        "column": start + 1,
                        "pattern": pattern.id,
                        "match": match.group(0),
                        "context": match_context,
                        "excerpt": _excerpt(line),
                        "note": pattern.note,
                        "reviewed": reviewed,
                    }

                    # Reviewed findings are accepted usages, not outstanding work:
                    # they stay out of `issues` so the lint count only ever
                    # reports what is left to do.
                    if reviewed:
                        reviewed_findings.append(finding)
                        continue

                    issues.append(finding)
                    by_context[match_context] = by_context.get(match_context, 0) + 1
                    by_pattern[pattern.id] = by_pattern.get(pattern.id, 0) + 1
                    by_source[pattern.source] = by_source.get(pattern.source, 0) + 1

    summary = {
        "findings": len(issues),
        "reviewed": len(reviewed_findings),
        "by_context": by_context,
        "by_pattern": by_pattern,
        "by_source": by_source,
        "disabled": disabled_ids,
        "reviewed_findings": reviewed_findings,
    }
    return issues, summary, unreadable


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@precondition(
    lambda kb_path, **_: isinstance(kb_path, (str, Path)) and str(kb_path).strip() != "",
    "kb_path must be non-empty",
)
@precondition(
    lambda kb_path, **_: Path(kb_path).is_dir(),
    "kb_path must be an existing KB directory",
)
def lint_kb(
    kb_path: str | Path,
    patterns_path: str | Path | None = None,
    style_enabled: bool = True,
) -> dict:
    """Run mechanical health checks on a KB.

    Returns a dict with 'issues' (list of issue dicts), a 'total_issues' count,
    and a 'style' summary.  Each issue has: type, file, message, and optionally
    target/details.

    'issues' and 'total_issues' carry outstanding work only, across every check.
    Style findings with a recorded review are accepted usages, so they are
    reported under 'style' ('reviewed', 'reviewed_findings') instead of being
    counted.  'total_issues' == 0 therefore means the KB is clean.
    """
    root = Path(kb_path)
    knowledge_dir = root / "knowledge"
    sources_dir = root / "sources"
    issues: list[dict] = []

    # Collect all knowledge .md files
    all_files = _collect_md_files(knowledge_dir)
    unreadable: dict[str, str] = {}
    unreadable_stems: set[str] = set()

    if all_files:
        # Collect source stubs as valid link targets (not scanned for content)
        source_stubs: set[str] = set()
        if sources_dir.exists():
            for f in sources_dir.rglob("*.md"):
                source_stubs.add(f.stem)

        # Build link graph: file_stem → set of targets it links to
        outgoing: dict[str, set[str]] = {}
        incoming: dict[str, set[str]] = {}

        for stem in all_files:
            outgoing[stem] = set()
            incoming.setdefault(stem, set())

        for stem, fpath in all_files.items():
            try:
                text = fpath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                unreadable.setdefault(fpath.relative_to(root).as_posix(), str(exc))
                unreadable_stems.add(stem)
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

        # Orphan pages (no incoming links).  Unreadable files are skipped: their
        # empty link sets come from the failed read, not from the file's content.
        for stem, fpath in all_files.items():
            if stem in unreadable_stems:
                continue
            if not incoming.get(stem):
                issues.append({
                    "type": "orphan",
                    "file": str(fpath.relative_to(root)),
                    "message": f"No incoming wikilinks to '{stem}'",
                })

        # Missing backlinks (A→B but B does not link back to A)
        for stem, targets in outgoing.items():
            for target in targets:
                if target in unreadable_stems:
                    continue
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

    if style_enabled:
        pattern_entries = effective_pattern_entries(
            kb_path=str(root),
            cli_patterns=patterns_path,
        )
        active_patterns = [p for p in pattern_entries if p.enabled]
        style_issues, style_summary, style_unreadable = _scan_style_files(
            root,
            active_patterns,
            load_review_records(str(root)),
            disabled_pattern_ids(pattern_entries),
        )
        for rel_path, message in style_unreadable.items():
            unreadable.setdefault(rel_path, message)
    else:
        style_issues = []
        style_summary = {
            "findings": 0,
            "reviewed": 0,
            "by_context": {},
            "by_pattern": {},
            "by_source": {},
            "disabled": [],
            "reviewed_findings": [],
        }

    # Deduplicated across both passes: a file unreadable by one is unreadable
    # by the other, and reporting it twice would overstate the work.
    unreadable_issues = [
        {
            "type": "unreadable-file",
            "file": rel_path,
            "message": f"Could not read markdown file: {message}",
        }
        for rel_path, message in sorted(unreadable.items())
    ]

    all_issues = issues + style_issues + unreadable_issues
    return {
        "issues": all_issues,
        "total_issues": len(all_issues),
        "style": style_summary,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Lint a knowledge base.")
    parser.add_argument("--path", required=True, help="Path to KB directory")
    parser.add_argument(
        "--output", "-o", type=Path,
        help="Write full JSON results to this file and emit a compact artifact envelope on stdout",
    )
    parser.add_argument(
        "--no-style",
        action="store_true",
        help="Disable style-phrase scanning.",
    )
    parser.add_argument(
        "--patterns", type=Path,
        help="Pattern file merged over default and per-KB settings.",
    )

    args = parser.parse_args(argv)

    try:
        result = lint_kb(
            args.path,
            patterns_path=args.patterns,
            style_enabled=not args.no_style,
        )
    except ContractViolationError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)

    emit_json_result(result, output_path=args.output, artifact_kind="kb-lint-results")


if __name__ == "__main__":
    main()
