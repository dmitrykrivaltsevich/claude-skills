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

Output: JSON to stdout.  Errors to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from contracts import ContractViolationError, precondition


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@precondition(
    lambda kb_path, source, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
def register_source(
    kb_path: str,
    source: str,
    is_reference: bool = False,
    title: str = "",
) -> dict:
    """Register a source in the KB.

    For local files (is_reference=False): copies file to sources/files/<src-id>/.
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
    next_id = config.get("next_source_id", 1)
    source_id = f"src-{next_id:03d}"

    if is_reference:
        # Create reference stub
        stub_path = root / "sources" / "references" / f"{source_id}.md"
        stub_path.parent.mkdir(parents=True, exist_ok=True)
        effective_title = title or source
        stub_content = f"""---
type: source-reference
source-id: {source_id}
location: {source}
title: {effective_title}
---

# {effective_title}

External source reference.

- **Location**: {source}
- **Source ID**: {source_id}
"""
        stub_path.write_text(stub_content, encoding="utf-8")

        # Update config
        config["sources"].append({
            "id": source_id,
            "type": "reference",
            "location": source,
            "title": effective_title,
            "original_name": "",
        })
        config["next_source_id"] = next_id + 1
        config_path.write_text(
            yaml.dump(config, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        return {
            "source_id": source_id,
            "type": "reference",
            "stub_path": str(stub_path),
        }

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

        # Update config
        effective_title = title or source_path.stem
        config["sources"].append({
            "id": source_id,
            "type": "file",
            "location": str(dest_file),
            "title": effective_title,
            "original_name": source_path.name,
        })
        config["next_source_id"] = next_id + 1
        config_path.write_text(
            yaml.dump(config, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        return {
            "source_id": source_id,
            "type": "file",
            "copied_to": str(dest_file),
            "original_name": source_path.name,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Register a source in the KB.")
    parser.add_argument("--kb-path", required=True, help="Path to KB directory")
    parser.add_argument("--source", required=True, help="File path or URL")
    parser.add_argument("--reference", action="store_true",
                        help="Create a reference stub instead of copying")
    parser.add_argument("--title", default="", help="Human-readable source title")

    args = parser.parse_args(argv)
    result = register_source(
        args.kb_path, args.source,
        is_reference=args.reference, title=args.title,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
