#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml >= 6.0",
# ]
# ///
"""Source registrar — copies or references source files into a KB.

For local files: copies to sources/files/<source-id>/.
For remote/uncopyable sources: creates a reference stub in sources/references/.
Updates the KB config registry with source metadata.

Source IDs follow first-author-year convention (e.g. real-2020, rumelhart-1986).
The caller provides the ID; this script validates uniqueness and format.

Output: JSON to stdout.  Errors to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from contracts import ContractViolationError, precondition

# Lowercase alphanumeric + hyphens, must start with a letter.
# Matches: real-2020, rumelhart-1986, karpathy-2023a, openai-2024-gpt4
_SOURCE_ID_RE = re.compile(r"^[a-z][a-z0-9]+(?:-[a-z0-9]+)+$")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@precondition(
    lambda kb_path, source, source_id, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
@precondition(
    lambda kb_path, source, source_id, **_: bool(_SOURCE_ID_RE.match(source_id)),
    "source_id must be kebab-case (e.g. real-2020, rumelhart-1986)",
)
def register_source(
    kb_path: str,
    source: str,
    source_id: str,
    is_reference: bool = False,
    title: str = "",
    identifiers: dict[str, str] | None = None,
) -> dict:
    """Register a source in the KB.

    For local files (is_reference=False): copies file to sources/files/<source-id>/.
    For references (is_reference=True): creates an MD stub in sources/references/.

    Updates .kb/config.yaml with source registry entry.
    """
    root = Path(kb_path)
    config_path = root / ".kb" / "config.yaml"

    if not config_path.exists():
        raise ContractViolationError(
            f"KB config not found: {config_path}", kind="precondition"
        )

    # Load config
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    # Validate source_id is unique
    existing_ids = {s["id"] for s in config.get("sources", [])}
    if source_id in existing_ids:
        raise ContractViolationError(
            f"source_id '{source_id}' already registered", kind="precondition"
        )

    # Build identifiers section for stubs (frontmatter + body)
    ids = identifiers or {}
    ids_fm_line = ""
    ids_body_lines = ""
    if ids:
        # YAML inline dict for frontmatter
        ids_yaml = yaml.dump({"identifiers": ids}, default_flow_style=False, sort_keys=True).strip()
        ids_fm_line = f"\n{ids_yaml}"
        # Human-readable lines for stub body
        ids_body_lines = "\n" + "\n".join(
            f"- **{k.upper()}**: {v}" for k, v in sorted(ids.items())
        )

    if is_reference:
        # Create reference stub
        stub_path = root / "sources" / "references" / f"{source_id}.md"
        stub_path.parent.mkdir(parents=True, exist_ok=True)
        effective_title = title or source
        stub_content = f"""---
type: source-reference
source-id: {source_id}
location: "{source}"
title: "{effective_title}"{ids_fm_line}
---

# {effective_title}

External source reference.

- **Location**: {source}
- **Source ID**: {source_id}
- **Analysis**: [[{source_id}-analysis]]{ids_body_lines}
"""
        stub_path.write_text(stub_content, encoding="utf-8")

        # Update config
        entry: dict = {
            "id": source_id,
            "type": "reference",
            "location": source,
            "title": effective_title,
            "original_name": "",
        }
        if ids:
            entry["identifiers"] = ids
        config["sources"].append(entry)
        config_path.write_text(
            yaml.dump(config, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        result: dict = {
            "source_id": source_id,
            "type": "reference",
            "stub_path": str(stub_path),
        }
        if ids:
            result["identifiers"] = ids
        return result

    else:
        # Local file — must exist
        source_path = Path(source)
        if not source_path.exists():
            raise ContractViolationError(
                f"Source file not found: {source}", kind="precondition"
            )

        # Copy to sources/files/<source-id>/
        dest_dir = root / "sources" / "files" / source_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / source_path.name
        shutil.copy2(str(source_path), str(dest_file))

        # Create navigable stub so [[source-id]] resolves in Obsidian
        effective_title = title or source_path.stem
        stub_path = root / "sources" / "files" / f"{source_id}.md"
        stub_content = f"""---
type: source-file
source-id: {source_id}
title: "{effective_title}"{ids_fm_line}
---

# {effective_title}

- **File**: {source_id}/{source_path.name}
- **Analysis**: [[{source_id}-analysis]]{ids_body_lines}
"""
        stub_path.write_text(stub_content, encoding="utf-8")

        # Update config
        entry = {
            "id": source_id,
            "type": "file",
            "location": str(dest_file),
            "title": effective_title,
            "original_name": source_path.name,
        }
        if ids:
            entry["identifiers"] = ids
        config["sources"].append(entry)
        config_path.write_text(
            yaml.dump(config, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        result = {
            "source_id": source_id,
            "type": "file",
            "copied_to": str(dest_file),
            "original_name": source_path.name,
        }
        if ids:
            result["identifiers"] = ids
        return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Register a source in the KB.")
    parser.add_argument("--kb-path", required=True, help="Path to KB directory")
    parser.add_argument("--source", required=True, help="File path or URL")
    parser.add_argument("--source-id", required=True,
                        help="Source ID in first-author-year format (e.g. real-2020)")
    parser.add_argument("--reference", action="store_true",
                        help="Create a reference stub instead of copying")
    parser.add_argument("--title", default="", help="Human-readable source title")
    parser.add_argument(
        "--identifier", action="append", default=[],
        metavar="TYPE:VALUE",
        help="Bibliographic identifier (repeatable). Format: type:value. "
             "Common types: isbn, doi, issn, arxiv, pmid, url",
    )

    args = parser.parse_args(argv)

    # Parse identifier flags into dict
    identifiers: dict[str, str] = {}
    for raw in args.identifier:
        if ":" not in raw:
            parser.error(f"Invalid identifier format (expected TYPE:VALUE): {raw}")
        key, value = raw.split(":", 1)
        identifiers[key.strip().lower()] = value.strip()

    result = register_source(
        args.kb_path, args.source,
        source_id=args.source_id,
        is_reference=args.reference, title=args.title,
        identifiers=identifiers or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
