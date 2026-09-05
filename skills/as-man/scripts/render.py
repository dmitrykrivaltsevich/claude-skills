#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Typeset a manual page for the terminal — the as-man display path.

Takes the markdown page Claude composed and lays it out the way `man` lays out
a real page: flush-left uppercase section headings, indented body, hard wrapping
at a fixed column, code blocks left alone.  Layout only.  This script makes no
decision about what to show; the caller has already chosen the section.

This is the one script in the skill that writes plain text to stdout rather than
JSON, because its output is what the reader sees.

Output: formatted text to stdout.  Errors to stderr.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))

from contracts import ContractViolationError, check_file_readable, precondition

# 80 columns is the width a manual page has been typeset at since nroff, and is
# the narrowest terminal still in common use.
DEFAULT_WIDTH = 80

# `man` indents section bodies by 7 columns and subsection headings by 3.
BODY_INDENT = 7
SUBSECTION_INDENT = 3

# Below this a wrapped line cannot hold a word plus the body indent, so the
# output would be unreadable rather than merely narrow.
MIN_WIDTH = 20

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
FENCE_RE = re.compile(r"^\s*```")
BULLET_RE = re.compile(r"^\s*([-*+]|\d+\.)\s+")

KEYS_HINT = "(h for keys)"
END_HINT = "(END — ! for gaps)"

# A read node is marked in the contents the way a pager marks a visited entry.
READ_MARK = "*"


# ---------------------------------------------------------------- page slicing


def _read_lines(file_path: Path) -> list[str]:
    check_file_readable(str(file_path))
    return Path(file_path).read_text(encoding="utf-8").splitlines()


def _section_lines(lines: list[str], heading: str) -> tuple[str, list[str]]:
    """Return the matched heading text and the lines below it, to the next peer."""
    wanted = heading.strip().casefold()

    start = None
    level = 0
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match and match.group(2).strip().casefold() == wanted:
            start = index
            level = len(match.group(1))
            break

    if start is None:
        raise ContractViolationError(f"Heading not found: {heading}", kind="precondition")

    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = HEADING_RE.match(lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break

    return HEADING_RE.match(lines[start]).group(2).strip(), lines[start + 1 : end]


# ---------------------------------------------------------------- typesetting


def _wrap(text: str, width: int, indent: int, hanging: int | None = None) -> list[str]:
    body_width = max(width - indent, MIN_WIDTH - indent)
    wrapped = textwrap.wrap(
        text,
        width=body_width,
        # URLs, file paths and identifiers must survive intact even when they
        # overflow; a broken path is worse than a long line.
        break_long_words=False,
        break_on_hyphens=False,
    )
    if not wrapped:
        return [""]
    pad = " " * indent
    hang = " " * (indent + (hanging or 0))
    return [pad + wrapped[0]] + [hang + line for line in wrapped[1:]]


def _typeset(lines: list[str], width: int) -> list[str]:
    """Lay out one section's body: paragraphs wrapped, code and lists preserved."""
    out: list[str] = []
    paragraph: list[str] = []
    in_fence = False

    def flush() -> None:
        if paragraph:
            out.extend(_wrap(" ".join(paragraph), width, BODY_INDENT))
            paragraph.clear()

    for line in lines:
        if FENCE_RE.match(line):
            flush()
            in_fence = not in_fence
            continue

        if in_fence:
            # Code is reproduced as written; wrapping it would change its meaning.
            out.append((" " * BODY_INDENT + line).rstrip())
            continue

        stripped = line.strip()

        if not stripped:
            flush()
            if out and out[-1] != "":
                out.append("")
            continue

        heading = HEADING_RE.match(line)
        if heading:
            flush()
            if out and out[-1] != "":
                out.append("")
            depth = len(heading.group(1))
            text = heading.group(2).strip()
            # Deeper headings are subsections; `man` indents them rather than
            # shouting them.
            out.append(" " * SUBSECTION_INDENT + text if depth >= 3 else text.upper())
            out.append("")
            continue

        bullet = BULLET_RE.match(line)
        if bullet:
            flush()
            marker = bullet.group(0).strip()
            rest = line.strip()[len(marker) :].strip()
            out.extend(_wrap(f"{marker} {rest}", width, BODY_INDENT, hanging=len(marker) + 1))
            continue

        if line.startswith("    ") or line.startswith("\t"):
            # Indented block: preformatted, like a code block without fences.
            flush()
            out.append((" " * BODY_INDENT + line.strip()).rstrip())
            continue

        paragraph.append(stripped)

    flush()

    while out and out[-1] == "":
        out.pop()
    return out


@precondition(
    lambda heading, **_: isinstance(heading, str) and heading.strip() != "",
    "heading must be a non-empty string",
)
@precondition(
    lambda width, **_: isinstance(width, int) and not isinstance(width, bool) and width >= MIN_WIDTH,
    f"width must be an integer of at least {MIN_WIDTH}",
)
def render_section(file_path: Path, *, heading: str, width: int = DEFAULT_WIDTH) -> str:
    """Render one section of the page as terminal text."""
    lines = _read_lines(file_path)
    matched, body = _section_lines(lines, heading)
    return "\n".join([matched.upper(), ""] + _typeset(body, width))


# ---------------------------------------------------------------- contents


@precondition(
    lambda outline, **_: isinstance(outline, dict) and isinstance(outline.get("children"), list),
    "outline must be the object returned by state.py outline, with a children list",
)
@precondition(
    lambda width, **_: isinstance(width, int) and not isinstance(width, bool) and width >= MIN_WIDTH,
    f"width must be an integer of at least {MIN_WIDTH}",
)
def render_contents(outline: dict[str, Any], *, width: int = DEFAULT_WIDTH) -> str:
    """Render a contents screen from one outline level."""
    children = outline["children"]
    out: list[str] = ["CONTENTS", ""]

    if not children:
        out.append(" " * BODY_INDENT + "(no entries)")
        return "\n".join(out)

    number_width = len(str(max(child.get("position", 0) for child in children)))

    for child in children:
        mark = READ_MARK if child.get("status") == "realised" else " "
        label = f"{mark} {str(child.get('position', '')).rjust(number_width)}. {child.get('heading', '')}"
        out.extend(_wrap(label, width, BODY_INDENT, hanging=number_width + 4))

        promise = str(child.get("promise", "")).strip()
        if promise:
            out.extend(_wrap(promise, width, BODY_INDENT + number_width + 4))
        out.append("")

    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


# ---------------------------------------------------------------- prompt line


@precondition(
    lambda name, **_: isinstance(name, str) and name.strip() != "",
    "name must be a non-empty string",
)
@precondition(
    lambda width, **_: isinstance(width, int) and not isinstance(width, bool) and width >= MIN_WIDTH,
    f"width must be an integer of at least {MIN_WIDTH}",
)
def prompt_line(
    *,
    name: str,
    position: str = "",
    section: str = "",
    end: bool = False,
    width: int = DEFAULT_WIDTH,
) -> str:
    """The single status line under a screen, in the style of `man`."""
    hint = END_HINT if end else KEYS_HINT
    left = "  ".join(part for part in (name, position, section) if part)

    room = width - len(hint) - 1
    if len(left) > room:
        left = left[: max(room, 0)].rstrip()

    padding = width - len(left) - len(hint)
    return left + " " * max(padding, 1) + hint


# ---------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Typeset a manual page for the terminal.")
    parser.add_argument("--file", type=Path, help="The composed markdown page")
    parser.add_argument("--section", help="Heading of the section to render")
    parser.add_argument("--toc-file", type=Path, help="JSON from `state.py outline`, rendered as contents")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help=f"Columns (default {DEFAULT_WIDTH})")
    parser.add_argument("--name", help="Page name for the prompt line, e.g. datalog(7)")
    parser.add_argument("--position", default="", help="Position for the prompt line, e.g. 12/27")
    parser.add_argument("--end", action="store_true", help="Mark this screen as the end of the page")
    args = parser.parse_args(argv)

    try:
        if args.toc_file:
            with open(args.toc_file, encoding="utf-8") as handle:
                outline = json.load(handle)
            body = render_contents(outline, width=args.width)
            label = "CONTENTS"
        elif args.file and args.section:
            body = render_section(args.file, heading=args.section, width=args.width)
            label = args.section.upper()
        else:
            raise ContractViolationError(
                "Provide --toc-file, or both --file and --section", kind="precondition"
            )

        print(body)

        if args.name:
            print()
            print(
                prompt_line(
                    name=args.name,
                    position=args.position,
                    section=label,
                    end=args.end,
                    width=args.width,
                )
            )
    except ContractViolationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
