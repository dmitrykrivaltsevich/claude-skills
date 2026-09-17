#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml >= 6.0",
# ]
# ///
"""KB opener — loads KB context for LLM priming.

Reads config, rules, index, recent log, file counts, and pending tasks.
Outputs a single JSON blob that primes the LLM to work with this KB.

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
from artifact_output import emit_json_result
from contracts import ContractViolationError, precondition

import vendor_skill
from vendor_skill import read_stamp

# Max lines of log to include in context — enough for recent activity
# without bloating the context window.
_MAX_LOG_LINES = 50  # ~50 lines ≈ last ~47 operations (one-line-per-op format)

# Top-level harness-owned config dirs — excluded from file/link stats so the
# vendored skill (.agents/skills/kb + aliases + agent file) never inflates
# KB overview numbers. Mirrors lint.py _STYLE_EXCLUDED_DIRS top-level names.
_HARNESS_DIRS = (".agents", ".claude", ".github")


def _is_kb_content(path: Path, root: Path) -> bool:
    """True for files that are KB content (not bookkeeping or harness config)."""
    rel = str(path.relative_to(root))
    if rel.startswith(".kb"):
        return False
    return path.relative_to(root).parts[0] not in _HARNESS_DIRS


def vendor_status(root: Path) -> dict:
    """Vendored-skill freshness for session priming: open.py is the mandated
    first op on every KB session, so staleness surfaces here with no new
    command and no new habit."""
    stamp = read_stamp(str(root))
    if stamp is None:
        return {"vendored": False, "version": None, "stale": False}
    version = stamp.get("version")
    # Module-attribute lookup (not a from-import binding) so tests and
    # future version bumps always compare against the live constant.
    return {
        "vendored": True,
        "version": version,
        "stale": version != vendor_skill.SKILL_VERSION,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@precondition(
    lambda kb_path, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
def open_kb(kb_path: str, stats: bool = False) -> dict:
    """Load KB context for LLM priming.

    Reads config, rules, index, recent log entries, file counts by category,
    and pending tasks.  With stats=True, also counts total files and wikilinks.
    """
    root = Path(kb_path)

    if not root.exists():
        raise ContractViolationError(
            f"KB path not found: {kb_path}", kind="precondition"
        )

    config_path = root / ".kb" / "config.yaml"
    if not config_path.exists():
        raise ContractViolationError(
            f"Not a valid KB directory (missing .kb/config.yaml): {kb_path}",
            kind="precondition",
        )

    # Config
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    # Rules
    rules_path = root / ".kb" / "rules.md"
    rules = rules_path.read_text(encoding="utf-8") if rules_path.exists() else ""

    # Index
    index_path = root / "index.md"
    index = index_path.read_text(encoding="utf-8") if index_path.exists() else ""

    # Recent log (last N lines)
    log_path = root / "log.md"
    recent_log = ""
    if log_path.exists():
        lines = log_path.read_text(encoding="utf-8").splitlines()
        recent_log = "\n".join(lines[-_MAX_LOG_LINES:])

    # File counts by knowledge category
    knowledge_dir = root / "knowledge"
    file_counts = {}
    if knowledge_dir.exists():
        for subdir in sorted(knowledge_dir.iterdir()):
            if subdir.is_dir():
                # Count .md files recursively
                count = sum(1 for _ in subdir.rglob("*.md"))
                file_counts[subdir.name] = count

    # Source count
    total_sources = len(config.get("sources", []))

    # Pending tasks
    tasks_dir = root / ".kb" / "tasks"
    pending_tasks = []
    if tasks_dir.exists():
        for f in sorted(tasks_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("phase", "") != "done":
                    pending_tasks.append({
                        "task_id": data["task_id"],
                        "task_type": data["task_type"],
                        "phase": data["phase"],
                        "description": data["description"],
                    })
            except (json.JSONDecodeError, KeyError):
                continue

    result = {
        "kb_path": str(root),
        "name": config.get("name", ""),
        "created": config.get("created", ""),
        "version": config.get("version", 1),
        "rules": rules,
        "index": index,
        "recent_log": recent_log,
        "file_counts": file_counts,
        "total_sources": total_sources,
        "pending_tasks": pending_tasks,
        "skill_vendor": vendor_status(root),
    }

    if stats:
        # Count total .md files across entire KB (excluding .kb/)
        total_files = sum(
            1 for f in root.rglob("*.md") if _is_kb_content(f, root)
        )

        # Count wikilinks across all .md files
        wikilink_re = re.compile(r"\[\[[^\]]+\]\]")
        total_links = 0
        for f in root.rglob("*.md"):
            if not _is_kb_content(f, root):
                continue
            try:
                text = f.read_text(encoding="utf-8")
                total_links += len(wikilink_re.findall(text))
            except (OSError, UnicodeDecodeError):
                continue

        result["total_files"] = total_files
        result["total_links"] = total_links

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Open a knowledge base.")
    parser.add_argument("--path", required=True, help="Path to the KB directory")
    parser.add_argument("--stats", action="store_true", help="Include file/link stats")
    parser.add_argument(
        "--output", "-o", type=Path,
        help="Write full JSON results to this file and emit a compact artifact envelope on stdout",
    )

    args = parser.parse_args(argv)
    result = open_kb(args.path, stats=args.stats)
    emit_json_result(result, output_path=args.output, artifact_kind="kb-open-context")


if __name__ == "__main__":
    main()
