#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
# ]
# ///
"""Portable skill vendor — makes a KB usable in any harness with zero install.

Copies the kb skill's runtime payload into the KB itself (canonical location
``.agents/skills/kb``), adds harness alias symlinks, and drops a Copilot
custom-agent pointer. The KB repo becomes self-contained: clone it, open it
in Claude Code / OpenCode / pi / Codex / Copilot / on github.com, and the
skill is already there.

Staleness is explicit, not silent: the vendored copy is stamped with the
skill version, ``check`` compares it against the installed skill, and
``open.py`` surfaces the flag every session. ``refresh`` re-converges.

Output: JSON to stdout.  Errors to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from contracts import ContractViolationError, precondition

# Skill version — carried in-skill because marketplace.json lives outside the
# skill tree and is unreachable from installed layouts (plugin managers copy
# skills elsewhere). Pinned equal to marketplace.json metadata.version by
# TestVersionPin: bump both together, the suite enforces it.
SKILL_VERSION = "1.10.0"

# Runtime payload: everything a harness needs to run the skill (entrypoint +
# helpers + docs). tests/ (~2.5MB of fixtures) and README.md stay out — a KB
# is a data repo, not a dev checkout; vendoring tests would tax every clone.
PAYLOAD = ("SKILL.md", "scripts", "references")

# Canonical location (agentskills.io standard): the ONE real copy. OpenCode,
# pi, Codex and Copilot read .agents/skills/ natively, so most harnesses need
# no alias at all.
_CANONICAL_REL = Path(".agents") / "skills" / "kb"

# Alias symlinks, name -> repo-relative link path. Every alias is a relative
# symlink (git preserves relative links on clone). When a harness starts
# reading .agents/skills/ natively, delete its row here — this table is the
# single place aliases are defined, so pruning is a one-line change.
ALIASES = {
    # Claude Code discovers project skills at .claude/skills/ only.
    "claude": Path(".claude") / "skills" / "kb",
}

# Copilot custom-agent pointer (.github/agents/kb.agent.md). A stub, not a
# fork: the body points at the vendored SKILL.md so the protocol has exactly
# one source of truth. Kept tiny on purpose (see TestAgentFile bound).
_AGENT_MD = """---
name: kb
description: Curate this repository's knowledge base — add and extract sources, query entries, lint and maintain structure. Use when the user asks about the knowledge base, its sources, entries, or gaps.
---
# KB Agent

This repository IS a knowledge base (kb skill). The KB root is this repo root.

1. Read `.agents/skills/kb/SKILL.md` and follow it — it is the full protocol.
   Scripts are data pipes (run via `uv run`); you do the intellectual work.
2. Run `open.py` first every session (`.agents/skills/kb/scripts/open.py`).
3. NEVER edit `.agents/skills/kb/` — it is a vendored copy. If the skill
   itself needs changing, propose it to the user instead.
4. If `open.py` reports `skill_vendor.stale: true`, tell the user to refresh
   the vendored skill from their installed kb skill, then continue.
"""

_SKILL_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_stamp(kb_path: str) -> dict | None:
    """Return the vendor stamp, or None when nothing is vendored."""
    stamp_path = Path(kb_path) / _CANONICAL_REL / ".vendor.json"
    if not stamp_path.is_file() or stamp_path.is_symlink():
        return None
    try:
        data = json.loads(stamp_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


@precondition(
    lambda kb_path, **_: len(str(kb_path).strip()) > 0,
    "kb_path must be non-empty",
)
def check(kb_path: str) -> dict:
    """Compare the vendored copy against the installed skill version."""
    stamp = read_stamp(kb_path)
    if stamp is None:
        return {
            "kb_path": str(kb_path),
            "vendored": False,
            "vendored_version": None,
            "installed_version": SKILL_VERSION,
            "stale": True,
            "detail": (
                "no vendored skill in this KB. Run vendor (or refresh) via "
                "the installed kb skill to make the KB portable."
            ),
        }
    vendored_version = stamp.get("version")
    fresh = vendored_version == SKILL_VERSION
    return {
        "kb_path": str(kb_path),
        "vendored": True,
        "vendored_version": vendored_version,
        "installed_version": SKILL_VERSION,
        "stale": not fresh,
        "detail": (
            "vendored skill is current."
            if fresh
            else (
                f"vendored skill is {vendored_version}, installed skill is "
                f"{SKILL_VERSION}. Run refresh (via the installed kb skill, "
                "never from the vendored copy) to re-converge."
            )
        ),
    }


def _refuse_self_vendor(kb_root: Path) -> None:
    """Refuse to vendor from inside the target KB's own vendored copy.

    Stamping the old version as current would be a silent lie: the source of
    a vendor operation must always be the installed skill, never the payload
    being replaced.
    """
    try:
        inside = kb_root.resolve() in _SKILL_ROOT.resolve().parents
    except OSError:
        inside = False
    if inside or _SKILL_ROOT.resolve() == (kb_root / _CANONICAL_REL).resolve():
        raise ContractViolationError(
            "refusing to vendor from inside the target KB's vendored copy "
            f"({_SKILL_ROOT}). Run vendor/refresh via the INSTALLED kb skill.",
            kind="precondition",
        )


@precondition(
    lambda kb_path, **_: len(str(kb_path).strip()) > 0,
    "kb_path must be non-empty",
)
@precondition(
    lambda kb_path, **_: Path(kb_path).is_dir(),
    "kb_path must be an existing KB directory — scaffold it first",
)
def vendor(kb_path: str, aliases: bool = True) -> dict:
    """Vendor the skill into the KB. Idempotent: replay changes zero bytes."""
    kb_root = Path(kb_path)
    _refuse_self_vendor(kb_root)

    canonical = kb_root / _CANONICAL_REL
    if canonical.is_symlink():
        raise ContractViolationError(
            f"refusing to vendor through symlinked dir: {canonical}. A planted "
            "link would pull KB writes outside the repo. Remove it manually.",
            kind="precondition",
        )
    if canonical.exists():
        shutil.rmtree(canonical)
    canonical.mkdir(parents=True)

    for entry in PAYLOAD:
        src = _SKILL_ROOT / entry
        if not src.exists():
            raise ContractViolationError(
                f"skill payload entry missing: {src}. Reinstall the skill.",
                kind="precondition",
            )
        dest = canonical / entry
        if src.is_dir():
            shutil.copytree(src, dest, copy_function=shutil.copy2)
        else:
            shutil.copy2(src, dest)

    # Stamp carries the version only — no timestamps — so replay is fixed
    # point: re-running vendor over its own output changes zero bytes.
    (canonical / ".vendor.json").write_text(
        json.dumps(
            {"skill": "kb", "version": SKILL_VERSION, "payload": list(PAYLOAD)},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    made_aliases: dict[str, str] = {}
    warnings: list[str] = []
    if aliases:
        for name in ALIASES:
            try:
                made_aliases[name] = add_alias(kb_path, name)["link"]
            except OSError as exc:
                # Windows without Developer Mode cannot create symlinks; the
                # canonical copy still serves every harness that reads
                # .agents/skills/ natively, so this is a warning, not a halt.
                warnings.append(f"alias {name} skipped: {exc}")

    agent_path = kb_root / ".github" / "agents" / "kb.agent.md"
    agent_path.parent.mkdir(parents=True, exist_ok=True)
    agent_path.write_text(_AGENT_MD, encoding="utf-8")

    return {
        "kb_path": str(kb_root),
        "version": SKILL_VERSION,
        "canonical": _CANONICAL_REL.as_posix(),
        "aliases": made_aliases,
        "agent": ".github/agents/kb.agent.md",
        "warnings": warnings,
    }


@precondition(
    lambda kb_path, **_: len(str(kb_path).strip()) > 0,
    "kb_path must be non-empty",
)
@precondition(
    lambda kb_path, **_: Path(kb_path).is_dir(),
    "kb_path must be an existing KB directory",
)
def refresh(kb_path: str) -> dict:
    """Re-copy payload + stamp after a skill upgrade. Aliases untouched: a
    user who unlinked an alias did so deliberately, refresh must not re-add."""
    kb_root = Path(kb_path)
    _refuse_self_vendor(kb_root)
    result = vendor(kb_path, aliases=False)
    result["aliases"] = "unchanged"
    return result


@precondition(
    lambda kb_path, **_: len(str(kb_path).strip()) > 0,
    "kb_path must be non-empty",
)
def unlink_aliases(kb_path: str) -> dict:
    """Remove alias symlinks only — canonical copy and agent file survive."""
    removed: list[str] = []
    skipped: list[str] = []
    for _name, rel in ALIASES.items():
        link = Path(kb_path) / rel
        if link.is_symlink():
            link.unlink()
            removed.append(rel.as_posix())
        else:
            skipped.append(rel.as_posix())
    return {"kb_path": str(kb_path), "removed": removed, "skipped": skipped}


@precondition(
    lambda kb_path, name, **_: len(str(kb_path).strip()) > 0,
    "kb_path must be non-empty",
)
@precondition(
    lambda kb_path, name, **_: len(str(name).strip()) > 0,
    "name must be non-empty",
)
def add_alias(kb_path: str, name: str) -> dict:
    """(Re)create one alias symlink. Unknown names fail with the valid set."""
    if name not in ALIASES:
        raise ContractViolationError(
            f"unknown alias {name!r}. Valid aliases: {sorted(ALIASES)}.",
            kind="precondition",
        )
    kb_root = Path(kb_path)
    link = kb_root / ALIASES[name]
    if link.exists() and not link.is_symlink():
        raise ContractViolationError(
            f"alias path occupied by a real file/dir: {link}. Move it aside "
            "first — vendor never clobbers user files.",
            kind="precondition",
        )
    if link.is_symlink():
        link.unlink()
    link.parent.mkdir(parents=True, exist_ok=True)
    target = os.path.relpath(kb_root / _CANONICAL_REL, link.parent)
    link.symlink_to(target)
    return {"kb_path": str(kb_root), "alias": name, "link": ALIASES[name].as_posix()}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Vendor the kb skill into a KB for harness portability."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_vendor = sub.add_parser("vendor", help="Copy skill + aliases + agent file")
    p_vendor.add_argument("--path", required=True, help="KB directory")
    p_vendor.add_argument(
        "--no-aliases", action="store_true", help="Skip alias symlinks"
    )

    p_check = sub.add_parser("check", help="Compare vendored vs installed version")
    p_check.add_argument("--path", required=True, help="KB directory")

    p_refresh = sub.add_parser("refresh", help="Re-converge after skill upgrade")
    p_refresh.add_argument("--path", required=True, help="KB directory")

    p_unlink = sub.add_parser("unlink-aliases", help="Remove alias symlinks only")
    p_unlink.add_argument("--path", required=True, help="KB directory")

    p_add = sub.add_parser("add-alias", help="(Re)create one alias symlink")
    p_add.add_argument("--path", required=True, help="KB directory")
    p_add.add_argument("--name", required=True, help="Alias name")

    args = parser.parse_args(argv)
    if args.command == "vendor":
        result = vendor(args.path, aliases=not args.no_aliases)
    elif args.command == "check":
        result = check(args.path)
    elif args.command == "refresh":
        result = refresh(args.path)
    elif args.command == "unlink-aliases":
        result = unlink_aliases(args.path)
    elif args.command == "add-alias":
        result = add_alias(args.path, args.name)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
