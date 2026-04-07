#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml >= 6.0",
# ]
# ///
"""KB scaffold — creates the directory structure and config for a new knowledge base.

Creates a complete KB folder tree with config, rules, index, and log files.

Output: JSON to stdout.  Errors to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from contracts import ContractViolationError, precondition

# ---------------------------------------------------------------------------
# KB directory tree — all folders that get created.
# ---------------------------------------------------------------------------

_KB_DIRS = [
    ".kb",
    ".kb/tasks",
    "sources/files",
    "sources/references",
    "knowledge/entities",
    "knowledge/topics",
    "knowledge/ideas",
    "knowledge/locations",
    "knowledge/timeline/years",
    "knowledge/timeline/months",
    "knowledge/timeline/days",
    "knowledge/sources",
    "knowledge/citations",
    "knowledge/controversies",
    "knowledge/meta",
]


# ---------------------------------------------------------------------------
# Template content
# ---------------------------------------------------------------------------

def _rules_md(name: str) -> str:
    """Generate the initial rules.md for a new KB."""
    return f"""# {name} — Rules

This file tells the LLM how to operate on this knowledge base.
It is co-evolved: the LLM may propose updates as the KB grows.

## Link Format

Use Obsidian wikilinks: `[[page-name]]` or `[[page-name|Display Text]]`.
File names use kebab-case (e.g. `albert-einstein.md`).

## Entry Types

Every knowledge file has YAML frontmatter with at minimum:

```yaml
---
type: <entry-type>
created: YYYY-MM-DD
updated: YYYY-MM-DD
source-ids: []
tags: []
---
```

### Entry types and their directories:

| Type | Directory | Description |
|------|-----------|-------------|
| entity | knowledge/entities/ | People, organizations |
| topic | knowledge/topics/ | Subject areas, fields, themes |
| idea | knowledge/ideas/ | Specific hypotheses, proposals, intellectual contributions |
| location | knowledge/locations/ | Places |
| timeline | knowledge/timeline/years,months,days/ | Temporal navigation entries |
| source-analysis | knowledge/sources/ | Per-source summary and analysis |
| citation | knowledge/citations/ | Citation graph (X cites Y in context Z) |
| controversy | knowledge/controversies/ | Contradictions with cross-references |
| meta | knowledge/meta/ | Cross-source meta-analyses |

## Timeline Entries

Year entries (`YYYY.md`) link to prev/next year and list months.
Month entries (`YYYY-MM.md`) link to prev/next month and list days.
Day entries (`YYYY-MM-DD.md`) link to prev/next day and list events.

## Citation Tracking

For academic/referenced sources:
- Catalog every in-text citation with exact context sentence
- Create entries for referenced works even if not in sources
- Track bibliography entries listed but never cited in context

## Controversies

When information contradicts existing KB entries:
- Create a controversy entry in knowledge/controversies/
- Cross-reference from ALL involved entries (bidirectional)
- Include the exact conflicting claims and their sources

## Sources

Raw source files live in sources/files/<source-id>/.
Reference stubs (for external/uncopyable sources) live in sources/references/.
Sources are immutable — never modify them.

## Index

index.md is the master catalog. Update it after every kb:add operation.
Organize entries by type with one-line summaries.

## Log

log.md is append-only. Each entry format:
`## [YYYY-MM-DD] <operation> | <title>`
"""


def _index_md(name: str) -> str:
    return f"""# {name} — Index

Master catalog of all knowledge base entries. The LLM reads this first for navigation.

## Entities

_No entries yet._

## Topics

_No entries yet._

## Ideas

_No entries yet._

## Locations

_No entries yet._

## Sources

_No entries yet._

## Citations

_No entries yet._

## Controversies

_No entries yet._

## Meta-Analyses

_No entries yet._

## Timeline

_No entries yet._
"""


def _log_md(name: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"""# {name} — Log

Chronological record of KB operations.

## [{now}] init | Knowledge base created
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@precondition(
    lambda kb_path, name, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
@precondition(
    lambda kb_path, name, **_: len(name.strip()) > 0,
    "name must be non-empty",
)
def scaffold_kb(kb_path: str, name: str) -> dict:
    """Create a new KB directory structure with config, rules, index, and log.

    Raises ContractViolationError if the KB path already contains a .kb/ directory.
    """
    root = Path(kb_path)

    if (root / ".kb" / "config.yaml").exists():
        raise ContractViolationError(
            f"KB already exists at {kb_path}", kind="precondition"
        )

    # Create directory tree
    for d in _KB_DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # config.yaml
    config = {
        "name": name,
        "created": now,
        "version": 1,  # KB schema version — bump on structure changes
        "link_format": "wikilink",  # Obsidian [[...]] format
        "next_source_id": 1,  # Auto-increment counter for source IDs
        "sources": [],  # Registry of added sources
    }
    (root / ".kb" / "config.yaml").write_text(
        yaml.dump(config, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    # rules.md
    (root / ".kb" / "rules.md").write_text(_rules_md(name), encoding="utf-8")

    # index.md
    (root / "index.md").write_text(_index_md(name), encoding="utf-8")

    # log.md
    (root / "log.md").write_text(_log_md(name), encoding="utf-8")

    return {
        "kb_path": str(root),
        "name": name,
        "created": now,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Scaffold a new knowledge base.")
    parser.add_argument("--path", required=True, help="Directory for the new KB")
    parser.add_argument("--name", required=True, help="Human-readable KB name")

    args = parser.parse_args(argv)
    result = scaffold_kb(args.path, args.name)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
