#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Research state manager — CRUD operations for persistent research state.

Manages a JSON state file that tracks the progress of a deep research session:
questions, sources, facts, and current phase. Supports resume — re-initializing
an existing research ID returns the current state without overwriting.

State location: ~/.cache/deep-research/<research-id>.json (overridable)

Output: JSON to stdout, or file-backed JSON plus a compact envelope when
``--output`` is provided. Errors go to stderr.
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
_DEFAULT_STATE_DIR = Path.home() / ".cache" / "deep-research"

# Valid research phases — ordered progression.
VALID_PHASES = ("scope", "sweep", "deep-read", "cross-reference", "synthesise")

# Valid question statuses.
VALID_QUESTION_STATUSES = ("unexplored", "partially", "covered")

_ARTIFACT_KINDS = {
    "init": "deep-research-state-init",
    "add-questions": "deep-research-state-add-questions",
    "update-question": "deep-research-state-update-question",
    "add-sources": "deep-research-state-add-sources",
    "add-facts": "deep-research-state-add-facts",
    "update-phase": "deep-research-state-update-phase",
    "status": "deep-research-state-status",
    "export": "deep-research-state-export",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _state_path(research_id: str, state_dir: Path) -> Path:
    """Compute the state file path for a research ID."""
    return state_dir / f"{research_id}.json"


def _load(research_id: str, state_dir: Path) -> dict:
    """Load state from disk.  Raises FileNotFoundError if missing."""
    path = _state_path(research_id, state_dir)
    if not path.exists():
        raise FileNotFoundError(f"No research state found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _save(research_id: str, data: dict, state_dir: Path) -> None:
    """Persist state to disk."""
    path = _state_path(research_id, state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@precondition(
    lambda research_id, goal, **_: len(research_id.strip()) > 0,
    "research_id must be non-empty",
)
@precondition(
    lambda research_id, goal, **_: len(goal.strip()) > 0,
    "goal must be non-empty",
)
def init_research(
    research_id: str,
    goal: str,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Initialize a new research session, or resume an existing one.

    If a state file already exists for research_id, returns it as-is
    with ``resumed: True``.  Otherwise creates a fresh state.
    """
    path = _state_path(research_id, state_dir)
    if path.exists():
        data = _load(research_id, state_dir)
        return {
            "research_id": data["research_id"],
            "state_file": str(path),
            "resumed": True,
        }

    data = {
        "research_id": research_id,
        "goal": goal,
        "phase": "scope",
        "questions": [],
        "sources": [],
        "facts": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save(research_id, data, state_dir)
    return {
        "research_id": research_id,
        "state_file": str(path),
        "resumed": False,
    }


@precondition(
    lambda research_id, questions, **_: len(questions) > 0,
    "At least one question is required",
)
def add_questions(
    research_id: str,
    questions: list[str],
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Add research questions.  Deduplicates by exact text match."""
    data = _load(research_id, state_dir)
    existing = {q["text"] for q in data["questions"]}
    for q_text in questions:
        if q_text not in existing:
            data["questions"].append({"text": q_text, "status": "unexplored"})
            existing.add(q_text)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save(research_id, data, state_dir)
    return {"total_questions": len(data["questions"])}


@precondition(
    lambda research_id, question_text, status, **_: status in VALID_QUESTION_STATUSES,
    f"status must be one of {VALID_QUESTION_STATUSES}",
)
def update_question(
    research_id: str,
    question_text: str,
    status: str,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Update the status of a specific question."""
    data = _load(research_id, state_dir)
    for q in data["questions"]:
        if q["text"] == question_text:
            q["status"] = status
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save(research_id, data, state_dir)
            return {"question": question_text, "status": status}

    raise ContractViolationError(
        f"Question not found: {question_text!r}", kind="precondition"
    )


@precondition(
    lambda research_id, sources, **_: len(sources) > 0,
    "At least one source is required",
)
def add_sources(
    research_id: str,
    sources: list[dict],
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Add sources (URL + metadata).  Deduplicates by URL."""
    data = _load(research_id, state_dir)
    existing_urls = {s["url"] for s in data["sources"]}
    next_id = len(data["sources"]) + 1

    for src in sources:
        url = src.get("url", "")
        if url and url not in existing_urls:
            data["sources"].append({
                "id": f"s{next_id}",
                "url": url,
                "title": src.get("title", ""),
                "skill": src.get("skill", ""),
            })
            existing_urls.add(url)
            next_id += 1

    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save(research_id, data, state_dir)
    return {"total_sources": len(data["sources"])}


@precondition(
    lambda research_id, facts, **_: len(facts) > 0,
    "At least one fact is required",
)
def add_facts(
    research_id: str,
    facts: list[dict],
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Add research facts (claims with source attribution and confidence)."""
    data = _load(research_id, state_dir)
    next_id = len(data["facts"]) + 1

    for fact in facts:
        data["facts"].append({
            "id": f"f{next_id}",
            "claim": fact.get("claim", ""),
            "source_ids": fact.get("source_ids", []),
            "confidence": fact.get("confidence", "medium"),
        })
        next_id += 1

    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save(research_id, data, state_dir)
    return {"total_facts": len(data["facts"])}


@precondition(
    lambda research_id, phase, **_: phase in VALID_PHASES,
    f"phase must be one of {VALID_PHASES}",
)
def update_phase(
    research_id: str,
    phase: str,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Update the current research phase."""
    data = _load(research_id, state_dir)
    data["phase"] = phase
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save(research_id, data, state_dir)
    return {"phase": phase}


def get_status(
    research_id: str,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Return a summary of research progress."""
    data = _load(research_id, state_dir)
    questions = data.get("questions", [])
    return {
        "research_id": data["research_id"],
        "goal": data["goal"],
        "phase": data["phase"],
        "total_questions": len(questions),
        "covered": sum(1 for q in questions if q["status"] == "covered"),
        "partially": sum(1 for q in questions if q["status"] == "partially"),
        "unexplored": sum(1 for q in questions if q["status"] == "unexplored"),
        "total_sources": len(data.get("sources", [])),
        "total_facts": len(data.get("facts", [])),
        "created_at": data.get("created_at", ""),
        "updated_at": data.get("updated_at", ""),
    }


def export_research(
    research_id: str,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Export the full research state."""
    return _load(research_id, state_dir)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _read_json_input(file_arg: str | None, inline_arg: str | None) -> list:
    """Read JSON from --file path, stdin ('-'), or inline --arg string.

    Priority: --file > inline arg.  Exits with an error if neither provided.
    Returns the parsed JSON (list of dicts, list of strings, or dict).
    """
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
    """Add arguments shared by all subcommands."""
    p.add_argument("--research-id", required=True)
    p.add_argument(
        "--state-dir", type=Path, default=_DEFAULT_STATE_DIR,
        help="Directory for state files.",
    )
    p.add_argument(
        "--output", "-o", type=Path,
        help="Write full JSON results to this file and emit a compact artifact envelope on stdout",
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entry point with subcommands for each operation."""
    parser = argparse.ArgumentParser(description="Research state manager.")
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init")
    _add_common_args(p_init)
    p_init.add_argument("--goal", required=True)

    # add-questions
    p_aq = sub.add_parser("add-questions")
    _add_common_args(p_aq)
    p_aq.add_argument("--questions", nargs="+", default=None,
                       help="Questions as separate args (short lists only)")
    p_aq.add_argument("--file", default=None, dest="questions_file",
                       help="Path to JSON array of question strings, or '-' for stdin")

    # update-question
    p_uq = sub.add_parser("update-question")
    _add_common_args(p_uq)
    p_uq.add_argument("--question", default=None, help="Question text (short only)")
    p_uq.add_argument("--status", required=True)
    p_uq.add_argument("--file", default=None, dest="uq_file",
                       help='Path to JSON object {"question": "...", "status": "..."}, or \'-\' for stdin')

    # add-sources
    p_as = sub.add_parser("add-sources")
    _add_common_args(p_as)
    p_as.add_argument("--sources", default=None, help="JSON array string (small data)")
    p_as.add_argument("--file", default=None, dest="sources_file",
                       help="Path to JSON file, or '-' for stdin (recommended for large data)")

    # add-facts
    p_af = sub.add_parser("add-facts")
    _add_common_args(p_af)
    p_af.add_argument("--facts", default=None, help="JSON array string (small data)")
    p_af.add_argument("--file", default=None, dest="facts_file",
                       help="Path to JSON file, or '-' for stdin (recommended for large data)")

    # update-phase
    p_up = sub.add_parser("update-phase")
    _add_common_args(p_up)
    p_up.add_argument("--phase", required=True)

    # status
    p_st = sub.add_parser("status")
    _add_common_args(p_st)

    # export
    p_ex = sub.add_parser("export")
    _add_common_args(p_ex)

    args = parser.parse_args(argv)
    state_dir = args.state_dir

    if args.command == "init":
        result = init_research(args.research_id, args.goal, state_dir=state_dir)
    elif args.command == "add-questions":
        if args.questions_file is not None:
            questions = _read_json_input(args.questions_file, None)
        elif args.questions is not None:
            questions = args.questions
        else:
            sys.exit("ERROR: provide --file PATH or --questions 'Q1' 'Q2'")
        result = add_questions(args.research_id, questions, state_dir=state_dir)
    elif args.command == "update-question":
        if args.uq_file is not None:
            uq_data = _read_json_input(args.uq_file, None)
            q_text = uq_data["question"]
            q_status = uq_data.get("status", args.status)
        elif args.question is not None:
            q_text = args.question
            q_status = args.status
        else:
            sys.exit("ERROR: provide --file PATH or --question 'text'")
        result = update_question(
            args.research_id, q_text, q_status, state_dir=state_dir
        )
    elif args.command == "add-sources":
        sources = _read_json_input(args.sources_file, args.sources)
        result = add_sources(args.research_id, sources, state_dir=state_dir)
    elif args.command == "add-facts":
        facts = _read_json_input(args.facts_file, args.facts)
        result = add_facts(args.research_id, facts, state_dir=state_dir)
    elif args.command == "update-phase":
        result = update_phase(args.research_id, args.phase, state_dir=state_dir)
    elif args.command == "status":
        result = get_status(args.research_id, state_dir=state_dir)
    elif args.command == "export":
        result = export_research(args.research_id, state_dir=state_dir)
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
