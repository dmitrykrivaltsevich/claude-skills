#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml >= 6.0",
# ]
# ///
"""Mechanical lint repairs — reciprocal backlinks + timeline stubs.

Consumes lint_kb() issues directly, so the fixer and the checker agree by
construction: a repair run followed by a lint run must report zero for the
covered categories. Style-phrase findings need judgment and stay agent-side.

Local imports: lint (checker, stdlib only), batch_merge (chain rebuild,
pyyaml), contracts and artifact_output (stdlib only) — so pyyaml is the
only runtime dependency.

Unit of work: one missing link / one missing date entry. Both entry points
are idempotent (rechecks before writing; reruns are no-ops) and support
--dry-run previews that write nothing.

Output: JSON to stdout (or --output artifact envelope). Errors to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from artifact_output import emit_json_result
from batch_merge import rebuild_timeline_chain
from contracts import ContractViolationError, precondition
from lint import lint_kb

# Section headings (in preference order) under which reciprocal links are
# appended — the repo's entry convention uses See also, Related as fallback.
_BACKLINK_SECTIONS = ("## See also", "## Related")

# Wikilink target pattern — same shape as lint.py/graph.py use for parsing.
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

# Expected stem shape per timeline level — anything else is left alone
# (a stray file in years/ is the LLM's to rename, not the filler's).
_TIMELINE_STEM_RES = {
    "years": re.compile(r"^\d{4}$"),
    "months": re.compile(r"^\d{4}-\d{2}$"),
    "days": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
}

# Timeline level directory per lint issue file prefix.
_TIMELINE_LEVEL_BY_PREFIX = {
    "knowledge/timeline/years/": "years",
    "knowledge/timeline/months/": "months",
    "knowledge/timeline/days/": "days",
}

_ARTIFACT_KINDS = {
    "backlinks": "kb-lint-fix-backlinks",
    "timeline": "kb-lint-fix-timeline",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _atomic_write_text(path: Path, text: str) -> None:
    """Unique-tmp + replace so interrupted repairs never halve a file."""
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=path.name + ".",
            delete=False,
        ) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
            tmp_name = handle.name
        os.replace(tmp_name, path)
    except OSError as exc:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
        raise ContractViolationError(
            f"cannot write {path}: {exc}. Check disk space and permissions.",
            kind="io",
        )


def _existing_targets(text: str) -> set[str]:
    return set(_WIKILINK_RE.findall(text))


def _insert_backlinks(text: str, stems: list[str]) -> str:
    """Append `- [[stem]]` bullets under See also (else Related, else a new
    section). Bare links only — never inside tables, never aliased."""
    return _ensure_section(text, "## See also", stems, fallback_order=_BACKLINK_SECTIONS)


def _ensure_section(
    text: str, heading: str, stems: list[str], fallback_order: tuple[str, ...] = ()
) -> str:
    """Ensure every stem has a `- [[stem]]` bullet under heading (created
    when absent). Existing bullets are never duplicated. Used both for
    reciprocal links and for timeline child sections (Months/Days), so new
    stubs never introduce the next round of missing backlinks."""
    lines = text.splitlines()
    existing = _existing_targets(text)
    missing = [s for s in stems if s not in existing]
    if not missing:
        return text if text.endswith("\n") else text + "\n"
    bullets = [f"- [[{stem}]]" for stem in missing]
    candidates = (heading, *[h for h in fallback_order if h != heading])
    anchor = next(
        (i for i, line in enumerate(lines) if line.strip() in candidates),
        None,
    )
    if anchor is None:
        return text.rstrip() + f"\n\n{heading}\n\n" + "\n".join(bullets) + "\n"
    end = anchor + 1
    while end < len(lines) and not lines[end].lstrip().startswith("#"):
        end += 1
    lines[end:end] = [*bullets]
    return "\n".join(lines) + "\n"


def _timeline_children(kb_path: str) -> dict[str, list[str]]:
    """Map every year stem -> sorted month stems, every month stem ->
    sorted day stems, from files present on disk (stubs included)."""
    root = Path(kb_path)
    months = sorted(
        p.stem
        for p in (root / "knowledge" / "timeline" / "months").glob("*.md")
    ) if (root / "knowledge" / "timeline" / "months").exists() else []
    days = sorted(
        p.stem
        for p in (root / "knowledge" / "timeline" / "days").glob("*.md")
    ) if (root / "knowledge" / "timeline" / "days").exists() else []
    by_year: dict[str, list[str]] = {}
    for month in months:
        if re.match(r"^\d{4}-\d{2}$", month):
            by_year.setdefault(month[:4], []).append(month)
    by_month: dict[str, list[str]] = {}
    for day in days:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", day):
            by_month.setdefault(day[:7], []).append(day)
    return {"years": by_year, "months": by_month}


def _stub_body(stem: str) -> str:
    today = _utc_today()
    return (
        "---\n"
        "type: timeline\n"
        f"created: {today}\n"
        f"updated: {today}\n"
        "source-ids: []\n"
        "tags: [stub]\n"
        "---\n\n"
        f"# {stem}\n"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@precondition(
    lambda kb_path, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
def fix_backlinks(kb_path: str, apply: bool = False) -> dict:
    """Add every missing reciprocal wikilink reported by lint_kb.

    With apply=False (default) reports the would-fix set and writes
    nothing. Rechecks targets at apply time, so reruns never duplicate.
    """
    try:
        report = lint_kb(kb_path, style_enabled=False)
    except (OSError, ValueError) as exc:
        raise ContractViolationError(
            f"lint failed on this KB: {exc}. Fix the underlying files first.",
            kind="io",
        )
    root = Path(kb_path)
    by_file: dict[str, set[str]] = {}
    for issue in report.get("issues", []):
        if issue.get("type") != "missing-backlink":
            continue
        by_file.setdefault(issue["file"], set()).add(issue["source"])
    edits: list[dict] = []
    for rel, sources in sorted(by_file.items()):
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ContractViolationError(
                f"cannot read link target {path}: {exc}.",
                kind="io",
            )
        have = _existing_targets(text)
        missing = sorted(s for s in sources if s not in have)
        if not missing:
            continue  # repaired since the lint snapshot — stays a no-op.
        edits.append({"file": rel, "added": missing})
        if apply:
            _atomic_write_text(path, _insert_backlinks(text, missing))
    return {
        "fixed": sum(len(e["added"]) for e in edits),
        "edits": edits,
        "dry_run": not apply,
    }


@precondition(
    lambda kb_path, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
def fix_timeline(kb_path: str, apply: bool = False) -> dict:
    """Create every missing timeline stub flagged by lint_kb, then repair
    the prev/next/parent chain across the touched levels.

    With apply=False (default) reports the would-create set and writes
    nothing. Stems that do not look like dates are reported under
    skipped, never created.
    """
    try:
        report = lint_kb(kb_path, style_enabled=False)
    except (OSError, ValueError) as exc:
        raise ContractViolationError(
            f"lint failed on this KB: {exc}. Fix the underlying files first.",
            kind="io",
        )
    root = Path(kb_path)
    wanted: dict[str, str] = {}  # rel path -> level
    for issue in report.get("issues", []):
        if issue.get("type") != "timeline-gap":
            continue
        details = issue.get("details") or {}
        missing = details.get("missing", "")
        level = _TIMELINE_LEVEL_BY_PREFIX.get(issue.get("file", ""))
        if not level or not missing:
            continue
        stem_re = _TIMELINE_STEM_RES[level]
        if not stem_re.match(missing):
            continue
        wanted[f"knowledge/timeline/{level}/{missing}.md"] = level
    created = sorted(wanted)
    skipped: list[str] = []
    sections_updated = 0
    if apply:
        for rel in created:
            _atomic_write_text(root / rel, _stub_body(Path(rel).stem))
        rebuild_timeline_chain(str(root))
        # New stubs link upward (parent) but nothing links down to them —
        # without child sections the stubs themselves become the next round
        # of missing backlinks. Ensured for ALL years/months (not just
        # created ones) so reruns and pre-existing stubs converge too.
        children = _timeline_children(str(root))
        for year, months in children["years"].items():
            path = root / "knowledge" / "timeline" / "years" / f"{year}.md"
            if path.exists():
                before = path.read_text(encoding="utf-8")
                after = _ensure_section(before, "## Months", months)
                if after != before:
                    _atomic_write_text(path, after)
                    sections_updated += 1
        for month, days in children["months"].items():
            path = root / "knowledge" / "timeline" / "months" / f"{month}.md"
            if path.exists():
                before = path.read_text(encoding="utf-8")
                after = _ensure_section(before, "## Days", days)
                if after != before:
                    _atomic_write_text(path, after)
                    sections_updated += 1
    return {
        "created": created,
        "skipped": skipped,
        "sections_updated": sections_updated,
        "dry_run": not apply,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Mechanical lint repairs.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_back = sub.add_parser("backlinks")
    p_back.add_argument("--kb-path", required=True)
    p_back.add_argument(
        "--apply", action="store_true", help="Write repairs (default: dry-run)"
    )
    p_back.add_argument("--output", "-o", type=Path, default=None)

    p_time = sub.add_parser("timeline")
    p_time.add_argument("--kb-path", required=True)
    p_time.add_argument(
        "--apply", action="store_true", help="Write repairs (default: dry-run)"
    )
    p_time.add_argument("--output", "-o", type=Path, default=None)

    args = parser.parse_args(argv)
    try:
        if args.command == "backlinks":
            result = fix_backlinks(args.kb_path, apply=args.apply)
        else:
            result = fix_timeline(args.kb_path, apply=args.apply)
    except ContractViolationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    emit_json_result(
        result,
        output_path=args.output,
        artifact_kind=_ARTIFACT_KINDS[args.command],
    )


if __name__ == "__main__":
    main()
