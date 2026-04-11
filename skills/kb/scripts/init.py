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
    "knowledge/questions",
    "knowledge/assets",
]


# ---------------------------------------------------------------------------
# Template content
# ---------------------------------------------------------------------------

def _rules_md(name: str) -> str:
    """Generate the initial rules.md for a new KB."""
    return f"""# {name} — Rules

This file tells the LLM how to operate on this knowledge base.
Update it when the KB develops conventions not covered by the generic SKILL.md.
Always propose changes to the user before modifying this file.

## Link Hygiene

Every wikilink MUST resolve to an existing file. Clicking a broken link in Obsidian
creates an empty file in the vault root, which destroys the KB structure.

- Wikilinks: `[[page-name]]` or `[[page-name|Display Text]]`. Internal KB only.
- External URLs: `[text](https://...)`. Never use wikilinks for external links.
- Source references in prose: `[[author-year-analysis]]`, never bare `author-year`.
- Source analysis files MUST include `**Source**: [[author-year]]` as a wikilink, never a file path.
- Source IDs in frontmatter `source-ids:` remain plain strings (not rendered).
- Every date in prose is a wikilink: `[[2017]]`, `[[2017-06]]`, `[[2017-06-12]]`.
  Create the timeline entry if it doesn't exist yet.
- Never write a wikilink unless the target exists or you create it now.
- File names use kebab-case (e.g. `albert-einstein.md`).

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
| question | knowledge/questions/ | Open questions, gaps, tensions between sources |

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

Source IDs use first-author-year convention: `real-2020`, `rumelhart-1986`.
If collision: add a letter suffix: `real-2020a`, `real-2020b`.
Raw source files live in sources/files/<source-id>/.
Reference stubs (for external/uncopyable sources) live in sources/references/.
Sources are immutable — never modify them.

## Index

index.md is the master catalog. Update it after every kb:add operation.
Organize entries by type with one-line summaries.

## Log

log.md is append-only. One line per operation:
`YYYY-MM-DD <op> <source-id> | <tally>`
Example: `2026-04-07 add vaswani-2017 | +10E +8T +4I +3TL`
Key: E=entities, T=topics, I=ideas, C=citations, TL=timeline. ~N=updated.
Details live in source analyses and task state — the log is a ledger, not a journal.

## Co-Evolution

Update this file when:
- The user corrects entry style or structure → record the preference
- A new entry type pattern emerges → add to the types table above
- The user establishes a tagging convention → document the taxonomy
- The user sets a scope boundary → add a scope section
- A naming conflict arises → add a disambiguation rule
- The KB outgrows current organization → add structural rules
- The user requests a custom workflow → document it here
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

## Questions

_No entries yet._

## Timeline

_No entries yet._
"""


def _log_md(name: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"""# {name} — Log

One line per operation. Details in source analyses and task state.

{now} init | KB created
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
