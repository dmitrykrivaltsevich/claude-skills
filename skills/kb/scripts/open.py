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
from contracts import ContractViolationError, precondition

# Max lines of log to include in context — enough for recent activity
# without bloating the context window.
_MAX_LOG_LINES = 50  # ~50 lines ≈ last 10-15 operations


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
    }

    if stats:
        # Count total .md files across entire KB (excluding .kb/)
        total_files = sum(
            1 for f in root.rglob("*.md")
            if not str(f.relative_to(root)).startswith(".kb")
        )

        # Count wikilinks across all .md files
        wikilink_re = re.compile(r"\[\[[^\]]+\]\]")
        total_links = 0
        for f in root.rglob("*.md"):
            if str(f.relative_to(root)).startswith(".kb"):
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

    args = parser.parse_args(argv)
    result = open_kb(args.path, stats=args.stats)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
