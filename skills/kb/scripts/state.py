#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Task state manager — multi-session task queue for KB operations.

Manages JSON state files that track progress of long-running KB tasks
(source ingestion, lint passes).  Supports resume — re-initializing an
existing task ID returns current state without overwriting.

State location: ~/.cache/kb/<task-id>.json  (overridable via --state-dir)

Output: JSON to stdout.  Errors to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from artifact_output import emit_json_result
from contracts import ContractViolationError, precondition

# Default state directory — user-scoped cache.
_DEFAULT_STATE_DIR = Path.home() / ".cache" / "kb"

# Valid task types — match KB operations that need multi-session tracking.
VALID_TASK_TYPES = ("add", "lint")

# Valid task phases — ordered progression for the add pipeline.
VALID_PHASES = (
    "registered",   # Source registered, task created
    "analyzing",    # LLM analyzing source structure (identifying chunks)
    "extracting",   # LLM extracting knowledge from chunks
    "citing",       # LLM building citation graph
    "cross-ref",    # LLM cross-referencing with existing KB
    "indexing",     # Updating index.md and log.md
    "done",         # Task complete
)

# Valid item statuses.
VALID_ITEM_STATUSES = ("pending", "in-progress", "done", "skipped")

_ARTIFACT_KINDS = {
    "init": "kb-task-init",
    "add-items": "kb-task-add-items",
    "update-item": "kb-task-update-item",
    "update-phase": "kb-task-update-phase",
    "status": "kb-task-status",
    "pending": "kb-task-pending",
    "list": "kb-task-list",
    "export": "kb-task-export",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _state_path(task_id: str, state_dir: Path) -> Path:
    return state_dir / f"{task_id}.json"


def _load(task_id: str, state_dir: Path) -> dict:
    path = _state_path(task_id, state_dir)
    if not path.exists():
        raise FileNotFoundError(f"No task state found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _save(task_id: str, data: dict, state_dir: Path) -> None:
    path = _state_path(task_id, state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@precondition(
    lambda task_id, task_type, description, kb_path, **_: len(task_id.strip()) > 0,
    "task_id must be non-empty",
)
@precondition(
    lambda task_id, task_type, description, kb_path, **_: task_type in VALID_TASK_TYPES,
    f"task_type must be one of {VALID_TASK_TYPES}",
)
@precondition(
    lambda task_id, task_type, description, kb_path, **_: len(description.strip()) > 0,
    "description must be non-empty",
)
def init_task(
    task_id: str,
    task_type: str,
    description: str,
    kb_path: str,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Initialize a new task, or resume an existing one.

    If a state file already exists for task_id, returns it as-is
    with ``resumed: True``.
    """
    path = _state_path(task_id, state_dir)
    if path.exists():
        data = _load(task_id, state_dir)
        return {
            "task_id": data["task_id"],
            "state_file": str(path),
            "resumed": True,
        }

    data = {
        "task_id": task_id,
        "task_type": task_type,
        "description": description,
        "kb_path": kb_path,
        "phase": "registered",
        "items": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save(task_id, data, state_dir)
    return {
        "task_id": task_id,
        "state_file": str(path),
        "resumed": False,
    }


@precondition(
    lambda task_id, items, **_: len(items) > 0,
    "At least one item is required",
)
def add_items(
    task_id: str,
    items: list[dict],
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Add work items to a task.  Deduplicates by title."""
    data = _load(task_id, state_dir)
    existing_titles = {it["title"] for it in data["items"]}
    next_id = len(data["items"]) + 1

    for item in items:
        title = item.get("title", "")
        if title and title not in existing_titles:
            data["items"].append({
                "id": f"i{next_id}",
                "title": title,
                "status": "pending",
            })
            existing_titles.add(title)
            next_id += 1

    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save(task_id, data, state_dir)
    return {"total_items": len(data["items"])}


@precondition(
    lambda task_id, item_id, status, **_: status in VALID_ITEM_STATUSES,
    f"status must be one of {VALID_ITEM_STATUSES}",
)
def update_item(
    task_id: str,
    item_id: str,
    status: str,
    notes: str | None = None,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Update the status of a specific work item.

    If *notes* is provided, it is stored on the item — use this to
    record a compact checkpoint of what was extracted so the LLM can
    resume after context compaction.
    """
    data = _load(task_id, state_dir)
    for item in data["items"]:
        if item["id"] == item_id:
            item["status"] = status
            if notes is not None:
                item["notes"] = notes
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save(task_id, data, state_dir)
            result: dict = {"item_id": item_id, "status": status}
            if notes is not None:
                result["notes"] = notes
            return result

    raise ContractViolationError(
        f"Item not found: {item_id!r}", kind="precondition"
    )


@precondition(
    lambda task_id, phase, **_: phase in VALID_PHASES,
    f"phase must be one of {VALID_PHASES}",
)
def update_phase(
    task_id: str,
    phase: str,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Update the current task phase."""
    data = _load(task_id, state_dir)
    data["phase"] = phase
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save(task_id, data, state_dir)
    return {"phase": phase}


def get_status(
    task_id: str,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Return a summary of task progress."""
    data = _load(task_id, state_dir)
    items = data.get("items", [])
    return {
        "task_id": data["task_id"],
        "task_type": data["task_type"],
        "description": data["description"],
        "kb_path": data["kb_path"],
        "phase": data["phase"],
        "total_items": len(items),
        "done": sum(1 for i in items if i["status"] == "done"),
        "pending": sum(1 for i in items if i["status"] == "pending"),
        "in_progress": sum(1 for i in items if i["status"] == "in-progress"),
        "skipped": sum(1 for i in items if i["status"] == "skipped"),
        "created_at": data.get("created_at", ""),
        "updated_at": data.get("updated_at", ""),
    }


def pending(
    task_id: str,
    limit: int | None = None,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Return pending work items (status == 'pending'), optionally limited.

    Also returns checkpoint notes from recently completed items so the
    LLM can reconstruct context after compaction.
    """
    data = _load(task_id, state_dir)
    pending_items = [
        {"id": i["id"], "title": i["title"]}
        for i in data["items"]
        if i["status"] == "pending"
    ]
    if limit is not None:
        pending_items = pending_items[:limit]

    # Last 5 completed items with their checkpoint notes — enough context
    # for the LLM to reconstruct what was already done.
    done_items = [
        i for i in data["items"]
        if i["status"] == "done" and i.get("notes")
    ]
    recent_done = [
        {"id": i["id"], "title": i["title"], "notes": i["notes"]}
        for i in done_items[-5:]  # last 5 keep the output compact
    ]

    return {
        "next_items": pending_items,
        "remaining": len([
            i for i in data["items"] if i["status"] == "pending"
        ]),
        "recent_completed": recent_done,
    }


def list_tasks(
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """List all tasks in the state directory."""
    state_dir.mkdir(parents=True, exist_ok=True)
    tasks = []
    for f in sorted(state_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            tasks.append({
                "task_id": data["task_id"],
                "task_type": data["task_type"],
                "phase": data["phase"],
                "description": data["description"],
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return {"tasks": tasks}


def export_task(
    task_id: str,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Export the full task state."""
    return _load(task_id, state_dir)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _read_json_input(file_arg: str | None, inline_arg: str | None) -> list:
    if file_arg is not None:
        if file_arg == "-":
            raw = sys.stdin.read()
        else:
            path = Path(file_arg)
            if not path.exists():
                sys.exit(f"ERROR: file not found: {path}")
            raw = path.read_text(encoding="utf-8")
        return json.loads(raw)

    if inline_arg is not None:
        return json.loads(inline_arg)

    sys.exit("ERROR: provide --file PATH (or '-' for stdin), or pass data inline")


def _add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--task-id", required=True)
    p.add_argument(
        "--state-dir", type=Path, default=_DEFAULT_STATE_DIR,
        help="Directory for state files.",
    )
    p.add_argument(
        "--output", "-o", type=Path,
        help="Write full JSON results to this file and emit a compact artifact envelope on stdout",
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="KB task state manager.")
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init")
    _add_common_args(p_init)
    p_init.add_argument("--task-type", required=True)
    p_init.add_argument("--description", required=True)
    p_init.add_argument("--kb-path", required=True)

    # add-items
    p_ai = sub.add_parser("add-items")
    _add_common_args(p_ai)
    p_ai.add_argument("--items", default=None, help="JSON array string")
    p_ai.add_argument("--file", default=None, dest="items_file")

    # update-item
    p_ui = sub.add_parser("update-item")
    _add_common_args(p_ui)
    p_ui.add_argument("--item-id", required=True)
    p_ui.add_argument("--status", required=True)
    p_ui.add_argument("--notes", default=None, help="Checkpoint notes for resumption")

    # update-phase
    p_up = sub.add_parser("update-phase")
    _add_common_args(p_up)
    p_up.add_argument("--phase", required=True)

    # status
    p_st = sub.add_parser("status")
    _add_common_args(p_st)

    # pending
    p_pe = sub.add_parser("pending")
    _add_common_args(p_pe)
    p_pe.add_argument("--limit", type=int, default=None)

    # list
    p_ls = sub.add_parser("list")
    p_ls.add_argument(
        "--state-dir", type=Path, default=_DEFAULT_STATE_DIR,
    )
    p_ls.add_argument(
        "--output", "-o", type=Path,
        help="Write full JSON results to this file and emit a compact artifact envelope on stdout",
    )

    # export
    p_ex = sub.add_parser("export")
    _add_common_args(p_ex)

    args = parser.parse_args(argv)
    state_dir = args.state_dir

    if args.command == "init":
        result = init_task(
            args.task_id, args.task_type, args.description,
            args.kb_path, state_dir=state_dir,
        )
    elif args.command == "add-items":
        items = _read_json_input(args.items_file, args.items)
        result = add_items(args.task_id, items, state_dir=state_dir)
    elif args.command == "update-item":
        result = update_item(
            args.task_id, args.item_id, args.status,
            notes=args.notes, state_dir=state_dir,
        )
    elif args.command == "update-phase":
        result = update_phase(args.task_id, args.phase, state_dir=state_dir)
    elif args.command == "status":
        result = get_status(args.task_id, state_dir=state_dir)
    elif args.command == "pending":
        result = pending(args.task_id, limit=args.limit, state_dir=state_dir)
    elif args.command == "list":
        result = list_tasks(state_dir=state_dir)
    elif args.command == "export":
        result = export_task(args.task_id, state_dir=state_dir)
    else:
        parser.print_help()
        sys.exit(1)

    emit_json_result(
        result,
        output_path=args.output,
        artifact_kind=_ARTIFACT_KINDS[args.command],
    )


if __name__ == "__main__":
    main()
