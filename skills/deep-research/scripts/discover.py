#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml >= 6.0",
# ]
# ///
"""Skill scanner — discovers installed skills and builds a capability map.

Scans a skills directory for SKILL.md files, parses their YAML frontmatter
and script decision tables, and outputs a JSON capability map to stdout.

Output: JSON array to stdout.  Each element describes one skill with its
name, description, and available commands (trigger → script → returns).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# Default location — sibling skills/ directory relative to this skill.
_DEFAULT_SKILLS_DIR = Path(__file__).resolve().parent.parent.parent


def parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from a SKILL.md string.

    Returns parsed dict, or empty dict if no frontmatter found.
    Uses a simple YAML subset parser to avoid heavy dependencies when
    full YAML isn't needed — handles string scalars and lists.
    """
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}

    raw = match.group(1)
    result: dict = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for line in raw.split("\n"):
        # List item under current key
        if current_key and re.match(r"^\s+-\s+", line):
            item = re.sub(r"^\s+-\s+", "", line).strip()
            if current_list is not None:
                current_list.append(item)
            continue

        # Flush any pending list
        if current_key and current_list is not None:
            result[current_key] = current_list
            current_list = None
            current_key = None

        # Key-value pair
        kv = re.match(r"^(\S[^:]*?):\s*(.*)", line)
        if kv:
            key = kv.group(1).strip()
            val = kv.group(2).strip()
            if val:
                result[key] = val
            else:
                # Start of a list or empty value
                current_key = key
                current_list = []

    # Flush trailing list
    if current_key and current_list is not None:
        result[current_key] = current_list

    return result


def extract_script_commands(text: str) -> list[dict]:
    """Extract script commands from markdown tables in SKILL.md.

    Looks for tables whose rows contain backtick-wrapped script references
    (e.g. ``search.py text``).  Returns list of dicts with trigger, script,
    and returns keys.
    """
    commands: list[dict] = []

    # Match markdown table rows: | cell | cell | cell |
    row_re = re.compile(r"^\|(.+)\|$", re.MULTILINE)
    rows = row_re.findall(text)

    # Track if we're in a table that has script-like content
    for row_text in rows:
        cells = [c.strip() for c in row_text.split("|")]
        # Skip separator rows (---|---|---)
        if all(re.match(r"^-+$", c) for c in cells if c):
            continue
        # Skip header rows
        if any(c.lower() in ("user says…", "user says...", "script", "what it returns") for c in cells):
            continue
        # Look for backtick-wrapped script names
        script_cell = None
        script_idx = -1
        for i, cell in enumerate(cells):
            backtick_match = re.search(r"`([^`]+\.py[^`]*)`", cell)
            if backtick_match:
                script_cell = backtick_match.group(1)
                script_idx = i
                break

        if script_cell is not None and len(cells) >= 3:
            # Heuristic: trigger is the cell before script, returns is the cell after
            trigger_idx = script_idx - 1 if script_idx > 0 else 0
            returns_idx = script_idx + 1 if script_idx + 1 < len(cells) else script_idx

            trigger = re.sub(r'^"|"$', "", cells[trigger_idx].strip())
            returns = cells[returns_idx].strip()

            commands.append({
                "trigger": trigger,
                "script": script_cell,
                "returns": returns,
            })

    return commands


def scan_skill(skill_dir: Path) -> dict | None:
    """Scan a single skill directory and return its capability descriptor.

    Returns None if the directory doesn't contain a SKILL.md.
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None

    text = skill_md.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(text)
    commands = extract_script_commands(text)

    name = frontmatter.get("name", skill_dir.name)
    description = frontmatter.get("description", "")

    return {
        "name": name,
        "description": description,
        "path": str(skill_dir),
        "commands": commands,
    }


def discover_skills(skills_dir: Path) -> list[dict]:
    """Scan all skill directories under skills_dir and return capability map.

    Returns a sorted list of skill descriptors.  Skips directories that
    don't contain a SKILL.md file.
    """
    if not skills_dir.exists():
        return []

    skills: list[dict] = []
    for child in sorted(skills_dir.iterdir()):
        if not child.is_dir():
            continue
        result = scan_skill(child)
        if result is not None:
            skills.append(result)

    return sorted(skills, key=lambda s: s["name"])


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Discover installed skills and output capability map as JSON."
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=_DEFAULT_SKILLS_DIR,
        help="Path to the skills/ directory to scan.",
    )
    args = parser.parse_args(argv)

    skills = discover_skills(args.skills_dir)
    print(json.dumps(skills, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
