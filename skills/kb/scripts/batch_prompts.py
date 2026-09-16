#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Delegation prompt renderer for parallel kb imports.

The main agent used to retype worker/lint-fix prompts (IDs, paths, contract
rules) on every run — toil that drifted by copy-paste. These canned
templates are filled from the batch manifest instead.

Placeholders use %%NAME%% tokens (never braces or $vars) so template prose
— CLI snippets, frontmatter examples, {handoff} shapes — can contain any
characters safely. ${CLAUDE_SKILL_DIR} is an intentional passthrough left
for the delegating agent's environment.

Local imports: contracts and artifact_output (stdlib only). The manifest is
read with a minimal local loader to keep this module dependency-free.

Output: rendered prompt text (stdout raw, or --output artifact envelope).
Errors to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from artifact_output import emit_json_result
from contracts import ContractViolationError, precondition

# Allowed leftover tokens: none. All %%TOKENS%% are substituted by the
# renderer (including %%SKILL_DIR%%, derived from this file's location),
# so a leftover token is always a template bug the tests catch.
_TOKEN_RE = re.compile(r"%%[A-Z_]+%%")

_ARTIFACT_KINDS = {
    "worker": "kb-batch-prompt-worker",
    "lint-fix": "kb-batch-prompt-lint-fix",
    "triangulate": "kb-batch-prompt-triangulate",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _template(name: str) -> str:
    path = Path(__file__).resolve().parent / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractViolationError(
            f"prompt template missing: {path}: {exc}. Reinstall the skill.",
            kind="io",
        )


def _manifest(kb_path: str, batch_id: str) -> dict:
    path = Path(kb_path) / ".kb" / "batches" / batch_id / "manifest.json"
    if not path.exists():
        raise ContractViolationError(
            f"no batch {batch_id!r} in this KB (missing {path}). "
            "Run batch_plan.py plan first.",
            kind="precondition",
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractViolationError(
            f"cannot read batch manifest {path}: {exc}.",
            kind="io",
        )
    if not isinstance(data, dict) or "order" not in data or "sources" not in data:
        raise ContractViolationError(
            f"batch manifest {path} is malformed (missing order/sources). "
            "Re-run batch_plan.py plan with a fresh batch-id.",
            kind="invariant",
        )
    return data


def _fill(template: str, values: dict[str, str], what: str) -> str:
    values = dict(values)
    # The skill directory derives from this file's location — no caller
    # input, no environment variable, nothing to drift.
    values.setdefault(
        "%%SKILL_DIR%%", str(Path(__file__).resolve().parent.parent)
    )
    rendered = template
    for token, replacement in values.items():
        rendered = rendered.replace(token, replacement)
    leftover = sorted(set(_TOKEN_RE.findall(rendered)))
    if leftover:
        raise ContractViolationError(
            f"prompt template for {what} leaves unsubstituted tokens: "
            f"{leftover}. Fix the template or the renderer.",
            kind="invariant",
        )
    return rendered


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@precondition(
    lambda kb_path, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
@precondition(
    lambda batch_id, **_: len(batch_id.strip()) > 0,
    "batch_id must be non-empty",
)
@precondition(
    lambda source_id, **_: len(source_id.strip()) > 0,
    "source_id must be non-empty",
)
def render_worker_prompt(kb_path: str, batch_id: str, source_id: str) -> str:
    """Render the Map-phase worker prompt for one source.

    Item id derives from manifest order (i1..iN) and the source file from
    the manifest entry — the caller supplies nothing but identities, so
    nothing can drift between plan and delegation.
    """
    manifest = _manifest(kb_path, batch_id)
    order: list = manifest["order"]
    if source_id not in order:
        raise ContractViolationError(
            f"source {source_id!r} is not part of batch {batch_id!r} "
            f"(order: {order}). Check the source-id spelling.",
            kind="precondition",
        )
    entry = next(s for s in manifest["sources"] if s["source_id"] == source_id)
    return _fill(
        _template("batch_worker_prompt.md"),
        {
            "%%KB_PATH%%": str(Path(kb_path)),
            "%%BATCH_ID%%": batch_id,
            "%%SOURCE_ID%%": source_id,
            "%%ITEM_ID%%": f"i{order.index(source_id) + 1}",
            "%%SOURCE_FILE%%": entry.get("location", ""),
            "%%INPUT_NAME%%": entry.get("input_name", entry.get("title", "")),
            "%%SOURCE_KIND%%": entry.get("kind", "file"),
        },
        what=f"worker {source_id}",
    )


@precondition(
    lambda kb_path, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
@precondition(
    lambda batch_id, **_: len(batch_id.strip()) > 0,
    "batch_id must be non-empty",
)
def render_lintfix_prompt(kb_path: str, batch_id: str) -> str:
    """Render the single final lint-repair prompt for a merged batch."""
    _manifest(kb_path, batch_id)  # existence check; content unneeded.
    return _fill(
        _template("batch_lintfix_prompt.md"),
        {
            "%%KB_PATH%%": str(Path(kb_path)),
            "%%BATCH_ID%%": batch_id,
        },
        what="lint-fix",
    )


@precondition(
    lambda kb_path, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
@precondition(
    lambda batch_id, **_: len(batch_id.strip()) > 0,
    "batch_id must be non-empty",
)
def render_triangulate_prompt(kb_path: str, batch_id: str) -> str:
    """Render the post-merge triangulation prompt (cross-source links,
    folds, meta entries, union-artifact cleanup). Runs after merge,
    before lint-fix — its link insertions are what the backlink pass
    then verifies."""
    manifest = _manifest(kb_path, batch_id)
    return _fill(
        _template("batch_triangulate_prompt.md"),
        {
            "%%KB_PATH%%": str(Path(kb_path)),
            "%%BATCH_ID%%": batch_id,
            "%%SOURCE_LIST%%": ", ".join(manifest["order"]),
        },
        what="triangulate",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Render batch prompts.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_worker = sub.add_parser("worker")
    p_worker.add_argument("--kb-path", required=True)
    p_worker.add_argument("--batch-id", required=True)
    p_worker.add_argument("--source-id", required=True)
    p_worker.add_argument("--output", "-o", type=Path, default=None)

    p_lint = sub.add_parser("lint-fix")
    p_lint.add_argument("--kb-path", required=True)
    p_lint.add_argument("--batch-id", required=True)
    p_lint.add_argument("--output", "-o", type=Path, default=None)

    p_tri = sub.add_parser("triangulate")
    p_tri.add_argument("--kb-path", required=True)
    p_tri.add_argument("--batch-id", required=True)
    p_tri.add_argument("--output", "-o", type=Path, default=None)

    args = parser.parse_args(argv)
    try:
        if args.command == "worker":
            prompt = render_worker_prompt(
                args.kb_path, args.batch_id, args.source_id
            )
        elif args.command == "lint-fix":
            prompt = render_lintfix_prompt(args.kb_path, args.batch_id)
        else:
            prompt = render_triangulate_prompt(args.kb_path, args.batch_id)
    except ContractViolationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    if args.output is None:
        print(prompt)
        return
    # --output stores the prompt text itself (reopenable artifact); stdout
    # carries a compact pointer, mirroring artifact-mode conventions.
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(prompt, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot write {args.output}: {exc}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"prompt_path": str(args.output)}))


if __name__ == "__main__":
    main()
