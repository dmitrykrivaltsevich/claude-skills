#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Session memory for the as-man viewer — outline tree, navigation, quiz, gaps.

Holds what Claude cannot keep across turns: the committed outline, which nodes
have been written, where the reader has been, the question bank, and the gap
findings.  The outline is a tree that is deepened lazily, so a concept page and
a 600-page book use the same schema at different depths.

Every command returns a bounded slice — one outline level, one node, one
question, the trail.  There is deliberately no command that dumps the whole
tree, because the caller is an LLM with a finite context window.

There is no `init`: the first write creates the session.

Output: JSON to stdout.  Errors to stderr.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))

from contracts import ContractViolationError, precondition

SCHEMA = "as-man/v1"

# The root node is implicit and always present; it is the parent of the top
# outline level and is never rendered as a section of its own.
ROOT_ID = "root"

# A node is `planned` once promised, `enumerated` once its children are known,
# and `realised` once its body has been written into page.md.
NODE_STATUSES = ("planned", "enumerated", "realised")

# Question types the reader is tested with.  See references/understanding-test.md
# for what each one is for; the script only checks membership.
QUESTION_TYPES = ("recall", "application", "discrimination", "consequence", "transfer", "trap")

# Grading is the LLM's job.  The script stores the verdict and counts it.
VERDICTS = ("correct", "partial", "incorrect")

GAP_KINDS = (
    "omission",
    "understated",
    "stale",
    "unstated-assumption",
    "conflict-of-interest",
    "contradicted",
)

MATERIALITY = ("high", "medium", "low")

# Fidelity levels describe how far the page departs from its source.
FIDELITY = ("verbatim", "adapt", "condense", "synthesize")

SOURCE_KINDS = ("topic", "source", "mixed")

# Trail entries are cheap, but a long reading session should not grow the state
# file without bound.  1000 steps is far more than any human session and still
# a trivial file size.
MAX_TRAIL = 1000


# ---------------------------------------------------------------- persistence


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _session_file(session_dir: Path) -> Path:
    return Path(session_dir) / "session.json"


def _new_session() -> dict[str, Any]:
    stamp = _now()
    return {
        "schema": SCHEMA,
        "created": stamp,
        "updated": stamp,
        "title": None,
        "manual_section": "7",
        "source": {"kind": None, "origin": None, "genre": None},
        "fidelity": None,
        "current": None,
        "trail": [],
        "nodes": {
            ROOT_ID: {
                "id": ROOT_ID,
                "parent": None,
                "heading": ROOT_ID,
                "level": 0,
                "promise": "",
                "status": "planned",
                "children": [],
                "line_start": None,
                "line_end": None,
            }
        },
        "questions": [],
        "attempts": [],
        "gaps": [],
    }


def _load(session_dir: Path) -> dict[str, Any]:
    path = _session_file(session_dir)
    if not path.is_file():
        raise ContractViolationError(
            f"No as-man session at {session_dir}. A session is created by the first write "
            f"(add-nodes); nothing has been written here yet.",
            kind="precondition",
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractViolationError(
            f"Session file is not valid JSON: {path} ({exc})", kind="invariant"
        ) from exc


def _load_or_create(session_dir: Path) -> dict[str, Any]:
    path = _session_file(session_dir)
    if path.is_file():
        return _load(session_dir)
    return _new_session()


def _save(session_dir: Path, doc: dict[str, Any]) -> None:
    doc["updated"] = _now()
    directory = Path(session_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = _session_file(directory)
    # Write and rename so an interrupted run cannot truncate a live session.
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, target)


# ---------------------------------------------------------------- node helpers


def _node(doc: dict[str, Any], node_id: str) -> dict[str, Any]:
    node = doc["nodes"].get(node_id)
    if node is None:
        raise ContractViolationError(f"Unknown node: {node_id}", kind="precondition")
    return node


def _slug(heading: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", heading.strip().lower()).strip("-")
    return slug or "node"


def _unique_id(doc: dict[str, Any], candidate: str) -> str:
    if candidate not in doc["nodes"]:
        return candidate
    suffix = 2
    while f"{candidate}-{suffix}" in doc["nodes"]:
        suffix += 1
    return f"{candidate}-{suffix}"


def _summarise(doc: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    """One outline row — never carries body text."""
    parent_id = node["parent"]
    siblings = doc["nodes"][parent_id]["children"] if parent_id else [node["id"]]
    return {
        "id": node["id"],
        "heading": node["heading"],
        "promise": node["promise"],
        "status": node["status"],
        "level": node["level"],
        "position": siblings.index(node["id"]) + 1,
        "sibling_count": len(siblings),
        "line_start": node["line_start"],
        "line_end": node["line_end"],
    }


def _resolve_position(doc: dict[str, Any], *, position: int, under: str | None) -> str:
    """Turn the number a reader sees in a contents screen into a node id."""
    parent_id = under
    if parent_id is None:
        current = doc.get("current")
        if current is None or current not in doc["nodes"]:
            raise ContractViolationError(
                "Cannot resolve a position without a level: pass under, or enter a node first",
                kind="precondition",
            )
        parent_id = doc["nodes"][current]["parent"]

    children = _node(doc, parent_id)["children"]
    if not children:
        raise ContractViolationError(
            f"Node '{parent_id}' has no children to number", kind="precondition"
        )
    if position > len(children):
        raise ContractViolationError(
            f"No entry {position} under '{parent_id}': valid range is 1 to {len(children)}",
            kind="precondition",
        )
    return children[position - 1]


def _is_end(doc: dict[str, Any], node: dict[str, Any]) -> bool:
    """True when no later sibling exists at this level or at any level above."""
    current = node
    while current["parent"] is not None:
        siblings = doc["nodes"][current["parent"]]["children"]
        if siblings.index(current["id"]) + 1 < len(siblings):
            return False
        current = doc["nodes"][current["parent"]]
    return True


# ---------------------------------------------------------------- add-nodes


def _valid_new_nodes(nodes: Any) -> bool:
    if not isinstance(nodes, list) or not nodes:
        return False
    for entry in nodes:
        if not isinstance(entry, dict):
            return False
        if not str(entry.get("heading", "")).strip():
            return False
        if not str(entry.get("promise", "")).strip():
            return False
    return True


@precondition(
    lambda parent, **_: isinstance(parent, str) and parent.strip() != "",
    "parent must be a non-empty node id",
)
@precondition(
    lambda nodes, **_: _valid_new_nodes(nodes),
    "nodes must be a non-empty list of objects, each with a non-empty heading and promise",
)
def add_nodes(session_dir: Path, *, parent: str, nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Commit the children of one node. Creates the session on first use."""
    doc = _load_or_create(session_dir)
    parent_node = _node(doc, parent)

    added: list[str] = []
    for entry in nodes:
        explicit = str(entry.get("id", "")).strip()
        if explicit:
            if explicit in doc["nodes"]:
                raise ContractViolationError(
                    f"Node id already exists: {explicit}", kind="precondition"
                )
            node_id = explicit
        else:
            node_id = _unique_id(doc, _slug(entry["heading"]))

        doc["nodes"][node_id] = {
            "id": node_id,
            "parent": parent,
            "heading": entry["heading"].strip(),
            "level": parent_node["level"] + 1,
            "promise": entry["promise"].strip(),
            "status": "planned",
            "children": [],
            "line_start": None,
            "line_end": None,
        }
        parent_node["children"].append(node_id)
        added.append(node_id)

    # Enumerating children is what turns a promised node into a container.
    if parent_node["status"] == "planned":
        parent_node["status"] = "enumerated"

    _save(session_dir, doc)
    return {
        "parent": parent,
        "added": added,
        "child_count": len(parent_node["children"]),
    }


# ---------------------------------------------------------------- outline


def outline(session_dir: Path, *, under: str = ROOT_ID) -> dict[str, Any]:
    """Return the children of one node — never the whole tree."""
    doc = _load(session_dir)
    parent_node = _node(doc, under)
    return {
        "parent": {
            "id": parent_node["id"],
            "heading": parent_node["heading"],
            "level": parent_node["level"],
            "status": parent_node["status"],
        },
        "children": [_summarise(doc, doc["nodes"][cid]) for cid in parent_node["children"]],
    }


# ---------------------------------------------------------------- enter


_NEXT_ACTION = {"planned": "realise", "enumerated": "contents", "realised": "render"}


@precondition(
    lambda node_id, position, **_: (node_id is None) != (position is None),
    "Provide exactly one of node id or position",
)
@precondition(
    lambda position, **_: position is None
    or (isinstance(position, int) and not isinstance(position, bool) and position >= 1),
    "position must be a positive integer, counting from 1",
)
def enter(
    session_dir: Path,
    *,
    node_id: str | None = None,
    position: int | None = None,
    under: str | None = None,
) -> dict[str, Any]:
    """Move to a node and report everything the navigation keys need.

    Address the target either by id, or by its position in a level — the
    number the reader sees in a contents screen. Without `under`, a position
    is resolved among the current node's siblings.
    """
    doc = _load(session_dir)

    if position is not None:
        node_id = _resolve_position(doc, position=position, under=under)

    node = _node(doc, node_id)

    if node_id == ROOT_ID:
        raise ContractViolationError(
            "Cannot enter the root node; it is the container of the top outline level",
            kind="precondition",
        )

    siblings = doc["nodes"][node["parent"]]["children"]
    index = siblings.index(node_id)

    doc["current"] = node_id
    doc["trail"].append({"id": node_id, "at": _now()})
    if len(doc["trail"]) > MAX_TRAIL:
        doc["trail"] = doc["trail"][-MAX_TRAIL:]
    _save(session_dir, doc)

    return {
        "node": _summarise(doc, node),
        "prev_id": siblings[index - 1] if index > 0 else None,
        "next_id": siblings[index + 1] if index + 1 < len(siblings) else None,
        "parent_id": node["parent"] if node["parent"] != ROOT_ID else None,
        "first_sibling_id": siblings[0],
        "last_sibling_id": siblings[-1],
        "sibling_headings": [doc["nodes"][sid]["heading"] for sid in siblings],
        "child_count": len(node["children"]),
        "is_end": _is_end(doc, node),
        "next_action": _NEXT_ACTION[node["status"]],
    }


# ---------------------------------------------------------------- realise


@precondition(
    lambda line_start, **_: isinstance(line_start, int) and not isinstance(line_start, bool) and line_start >= 1,
    "line_start must be a positive integer",
)
@precondition(
    lambda line_start, line_end, **_: isinstance(line_end, int)
    and not isinstance(line_end, bool)
    and line_end >= line_start,
    "line_end must be an integer not less than line_start",
)
def realise(session_dir: Path, *, node_id: str, line_start: int, line_end: int) -> dict[str, Any]:
    """Record that a node's body has been written into page.md."""
    doc = _load(session_dir)
    node = _node(doc, node_id)

    node["status"] = "realised"
    node["line_start"] = line_start
    node["line_end"] = line_end
    _save(session_dir, doc)

    return {"node": _summarise(doc, node)}


# ---------------------------------------------------------------- trail


@precondition(
    lambda limit, **_: limit is None or (isinstance(limit, int) and limit >= 1),
    "limit must be a positive integer",
)
def trail(session_dir: Path, *, limit: int | None = None) -> dict[str, Any]:
    """The reading path, most recent last — used to shape the next body."""
    doc = _load(session_dir)
    steps = doc["trail"][-limit:] if limit else doc["trail"]
    return {
        "trail": [
            {"id": step["id"], "heading": doc["nodes"][step["id"]]["heading"], "at": step["at"]}
            for step in steps
            if step["id"] in doc["nodes"]
        ],
        "step_count": len(doc["trail"]),
    }


# ---------------------------------------------------------------- quiz


def _valid_questions(questions: Any) -> bool:
    if not isinstance(questions, list) or not questions:
        return False
    for entry in questions:
        if not isinstance(entry, dict):
            return False
        for field in ("node_id", "question", "answer_key"):
            if not str(entry.get(field, "")).strip():
                return False
        if entry.get("type") not in QUESTION_TYPES:
            return False
    return True


@precondition(
    lambda questions, **_: _valid_questions(questions),
    "questions must be a non-empty list of objects with node_id, type, question and answer_key; "
    f"type must be one of {QUESTION_TYPES}",
)
def quiz_add(session_dir: Path, *, questions: list[dict[str, Any]]) -> dict[str, Any]:
    """Seed the question bank. Only realised nodes may be quizzed."""
    doc = _load(session_dir)

    existing = {q["id"] for q in doc["questions"]}
    added: list[str] = []
    for entry in questions:
        node = _node(doc, entry["node_id"])
        if node["status"] != "realised":
            raise ContractViolationError(
                f"Cannot quiz node '{node['id']}' ({node['status']}): the reader has not seen it. "
                f"Only realised nodes may be quizzed.",
                kind="precondition",
            )

        explicit = str(entry.get("id", "")).strip()
        question_id = explicit or f"q{len(doc['questions']) + len(added) + 1}"
        if question_id in existing:
            raise ContractViolationError(
                f"Question id already exists: {question_id}", kind="precondition"
            )

        doc["questions"].append(
            {
                "id": question_id,
                "node_id": entry["node_id"],
                "type": entry["type"],
                "question": entry["question"].strip(),
                "answer_key": entry["answer_key"].strip(),
            }
        )
        existing.add(question_id)
        added.append(question_id)

    _save(session_dir, doc)
    return {"added": added, "added_count": len(added), "bank_size": len(doc["questions"])}


def _node_scores(doc: dict[str, Any]) -> dict[str, int]:
    """Correct minus incorrect per node. Lower is weaker."""
    by_question = {q["id"]: q["node_id"] for q in doc["questions"]}
    scores: dict[str, int] = {}
    for attempt in doc["attempts"]:
        node_id = by_question.get(attempt["question_id"])
        if node_id is None:
            continue
        delta = {"correct": 1, "partial": 0, "incorrect": -1}[attempt["verdict"]]
        scores[node_id] = scores.get(node_id, 0) + delta
    return scores


def _document_order(doc: dict[str, Any]) -> dict[str, int]:
    """Depth-first position of every node, for a deterministic tie-break."""
    order: dict[str, int] = {}

    def walk(node_id: str) -> None:
        order[node_id] = len(order)
        for child in doc["nodes"][node_id]["children"]:
            walk(child)

    walk(ROOT_ID)
    return order


@precondition(
    lambda count, **_: isinstance(count, int) and not isinstance(count, bool) and count >= 1,
    "count must be a positive integer",
)
def quiz_next(session_dir: Path, *, count: int = 1) -> dict[str, Any]:
    """Pick the next unanswered questions, weakest node first."""
    doc = _load(session_dir)

    answered = {attempt["question_id"] for attempt in doc["attempts"]}
    scores = _node_scores(doc)
    order = _document_order(doc)

    pending = [
        q
        for q in doc["questions"]
        if q["id"] not in answered and doc["nodes"][q["node_id"]]["status"] == "realised"
    ]
    pending.sort(
        key=lambda q: (
            scores.get(q["node_id"], 0),
            order.get(q["node_id"], 0),
            doc["questions"].index(q),
        )
    )

    picked = []
    for question in pending[:count]:
        node = doc["nodes"][question["node_id"]]
        picked.append(
            {
                **question,
                "heading": node["heading"],
                "line_start": node["line_start"],
                "line_end": node["line_end"],
            }
        )

    return {"questions": picked, "pending_count": len(pending)}


@precondition(
    lambda verdict, **_: verdict in VERDICTS,
    f"verdict must be one of {VERDICTS}",
)
def quiz_record(
    session_dir: Path, *, question_id: str, verdict: str, note: str | None = None
) -> dict[str, Any]:
    """Persist a verdict the LLM assigned. The script never grades."""
    doc = _load(session_dir)

    question = next((q for q in doc["questions"] if q["id"] == question_id), None)
    if question is None:
        raise ContractViolationError(f"Unknown question: {question_id}", kind="precondition")

    doc["attempts"].append(
        {
            "question_id": question_id,
            "node_id": question["node_id"],
            "verdict": verdict,
            "note": note,
            "at": _now(),
        }
    )
    _save(session_dir, doc)

    node = doc["nodes"][question["node_id"]]
    return {
        "question_id": question_id,
        "verdict": verdict,
        "node_id": question["node_id"],
        "heading": node["heading"],
        "line_start": node["line_start"],
        "line_end": node["line_end"],
        "attempt_count": len(doc["attempts"]),
    }


def quiz_report(session_dir: Path) -> dict[str, Any]:
    """Verdict counts per node, and which nodes deserve a re-read."""
    doc = _load(session_dir)

    tally: dict[str, dict[str, int]] = {}
    for attempt in doc["attempts"]:
        row = tally.setdefault(
            attempt["node_id"], {"correct": 0, "partial": 0, "incorrect": 0}
        )
        row[attempt["verdict"]] += 1

    order = _document_order(doc)
    by_node = [
        {
            "node_id": node_id,
            "heading": doc["nodes"][node_id]["heading"],
            "line_start": doc["nodes"][node_id]["line_start"],
            "line_end": doc["nodes"][node_id]["line_end"],
            **counts,
        }
        for node_id, counts in sorted(tally.items(), key=lambda kv: order.get(kv[0], 0))
    ]

    answered = {attempt["question_id"] for attempt in doc["attempts"]}
    return {
        "by_node": by_node,
        "weak_nodes": [
            row["node_id"] for row in by_node if row["incorrect"] > 0 or row["partial"] > 0
        ],
        "asked_count": len(answered),
        "bank_size": len(doc["questions"]),
    }


# ---------------------------------------------------------------- gaps


def _valid_gaps(gaps: Any) -> bool:
    if not isinstance(gaps, list) or not gaps:
        return False
    for entry in gaps:
        if not isinstance(entry, dict):
            return False
        for field in ("fingerprint", "title", "missing", "effect"):
            if not str(entry.get(field, "")).strip():
                return False
        if entry.get("kind") not in GAP_KINDS:
            return False
        if entry.get("materiality") not in MATERIALITY:
            return False
    return True


@precondition(
    lambda gaps, **_: _valid_gaps(gaps),
    "gaps must be a non-empty list of objects with fingerprint, title, missing, effect, "
    f"kind (one of {GAP_KINDS}) and materiality (one of {MATERIALITY})",
)
def gaps_add(session_dir: Path, *, gaps: list[dict[str, Any]]) -> dict[str, Any]:
    """Record gap findings, deduplicated by fingerprint."""
    doc = _load(session_dir)

    known = {gap["fingerprint"] for gap in doc["gaps"]}
    added: list[str] = []
    for entry in gaps:
        fingerprint = entry["fingerprint"].strip()
        if fingerprint in known:
            continue
        evidence = str(entry.get("evidence", "")).strip()
        doc["gaps"].append(
            {
                "fingerprint": fingerprint,
                "kind": entry["kind"],
                "materiality": entry["materiality"],
                "title": entry["title"].strip(),
                "missing": entry["missing"].strip(),
                "effect": entry["effect"].strip(),
                "evidence": evidence or None,
                # No source means the claim rests on model knowledge alone, and the
                # rendered GAPS section must say so.
                "verified": bool(evidence),
                "at": _now(),
            }
        )
        known.add(fingerprint)
        added.append(fingerprint)

    _save(session_dir, doc)
    return {"added": added, "added_count": len(added), "gap_count": len(doc["gaps"])}


def gaps_list(session_dir: Path) -> dict[str, Any]:
    """Every recorded gap, most material first."""
    doc = _load(session_dir)
    rank = {level: index for index, level in enumerate(MATERIALITY)}
    return {
        "gaps": sorted(doc["gaps"], key=lambda gap: rank.get(gap["materiality"], 99)),
        "gap_count": len(doc["gaps"]),
        "unverified_count": sum(1 for gap in doc["gaps"] if not gap["verified"]),
    }


# ---------------------------------------------------------------- describe


@precondition(
    lambda kind, **_: kind is None or kind in SOURCE_KINDS,
    f"kind must be one of {SOURCE_KINDS}",
)
@precondition(
    lambda fidelity, **_: fidelity is None or fidelity in FIDELITY,
    f"fidelity must be one of {FIDELITY}",
)
def describe(
    session_dir: Path,
    *,
    title: str | None = None,
    manual_section: str | None = None,
    kind: str | None = None,
    origin: str | None = None,
    genre: str | None = None,
    fidelity: str | None = None,
) -> dict[str, Any]:
    """Record what this page is and how far it departs from its source."""
    doc = _load_or_create(session_dir)

    if title is not None:
        doc["title"] = title.strip()
    if manual_section is not None:
        doc["manual_section"] = manual_section.strip()
    if kind is not None:
        doc["source"]["kind"] = kind
    if origin is not None:
        doc["source"]["origin"] = origin.strip()
    if genre is not None:
        doc["source"]["genre"] = genre.strip()
    if fidelity is not None:
        doc["fidelity"] = fidelity

    _save(session_dir, doc)
    return {
        "title": doc["title"],
        "manual_section": doc["manual_section"],
        "source": doc["source"],
        "fidelity": doc["fidelity"],
    }


# ---------------------------------------------------------------- status


def status(session_dir: Path) -> dict[str, Any]:
    """Progress summary. Never returns the tree itself."""
    doc = _load(session_dir)
    nodes = doc["nodes"]

    counts = {name: 0 for name in NODE_STATUSES}
    for node in nodes.values():
        if node["id"] != ROOT_ID:
            counts[node["status"]] += 1

    current = doc["current"]
    return {
        "title": doc["title"],
        "manual_section": doc["manual_section"],
        "source": doc["source"],
        "fidelity": doc["fidelity"],
        "current": current,
        "current_heading": nodes[current]["heading"] if current in nodes else None,
        "node_count": len(nodes),
        "realised_count": counts["realised"],
        "by_status": counts,
        "max_depth": max(node["level"] for node in nodes.values()),
        "trail_length": len(doc["trail"]),
        "bank_size": len(doc["questions"]),
        "attempt_count": len(doc["attempts"]),
        "gap_count": len(doc["gaps"]),
    }


# ---------------------------------------------------------------- CLI


def _default_session_dir(session_id: str) -> Path:
    return Path.home() / ".cache" / "as-man" / session_id


def _resolve_dir(args: argparse.Namespace) -> Path:
    if args.session_dir:
        return Path(args.session_dir)
    if not args.session_id:
        raise ContractViolationError(
            "Provide --session-id or --session-dir", kind="precondition"
        )
    return _default_session_dir(args.session_id)


def _read_json_file(path: Path) -> Any:
    if not Path(path).is_file():
        raise ContractViolationError(f"File does not exist: {path}", kind="precondition")
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractViolationError(f"Not valid JSON: {path} ({exc})", kind="precondition") from exc


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="as-man session memory.")
    parser.add_argument("--session-id", help="Session name under ~/.cache/as-man/")
    parser.add_argument("--session-dir", help="Explicit session directory (overrides --session-id)")

    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add-nodes", help="Commit the children of one node")
    p_add.add_argument("--parent", default=ROOT_ID)
    p_add.add_argument("--file", required=True, type=Path, help="JSON array of {id?, heading, promise}")

    p_outline = sub.add_parser("outline", help="Children of one node")
    p_outline.add_argument("--under", default=ROOT_ID)

    p_enter = sub.add_parser("enter", help="Move to a node, by id or by position")
    p_enter.add_argument("--id", help="Target node id")
    p_enter.add_argument("--position", type=int, help="Target position in a level, counting from 1")
    p_enter.add_argument("--under", help="Level the position counts within (default: the current level)")

    p_realise = sub.add_parser("realise", help="Mark a body written")
    p_realise.add_argument("--id", required=True)
    p_realise.add_argument("--line-start", required=True, type=int)
    p_realise.add_argument("--line-end", required=True, type=int)

    p_trail = sub.add_parser("trail", help="The reading path")
    p_trail.add_argument("--limit", type=int)

    p_quiz_add = sub.add_parser("quiz-add", help="Seed the question bank")
    p_quiz_add.add_argument("--file", required=True, type=Path)

    p_quiz_next = sub.add_parser("quiz-next", help="Pick the next questions")
    p_quiz_next.add_argument("--count", type=int, default=1)

    p_quiz_record = sub.add_parser("quiz-record", help="Persist a verdict")
    p_quiz_record.add_argument("--question-id", required=True)
    p_quiz_record.add_argument("--verdict", required=True, choices=list(VERDICTS))
    p_quiz_record.add_argument("--note")

    sub.add_parser("quiz-report", help="Verdict counts per node")

    p_gaps_add = sub.add_parser("gaps-add", help="Record gap findings")
    p_gaps_add.add_argument("--file", required=True, type=Path)

    sub.add_parser("gaps-list", help="Recorded gaps, most material first")

    p_describe = sub.add_parser("describe", help="Record what this page is")
    p_describe.add_argument("--title")
    p_describe.add_argument("--manual-section")
    p_describe.add_argument("--kind", choices=list(SOURCE_KINDS))
    p_describe.add_argument("--origin")
    p_describe.add_argument("--genre")
    p_describe.add_argument("--fidelity", choices=list(FIDELITY))

    sub.add_parser("status", help="Progress summary")

    args = parser.parse_args(argv)

    try:
        session_dir = _resolve_dir(args)

        if args.command == "add-nodes":
            result = add_nodes(session_dir, parent=args.parent, nodes=_read_json_file(args.file))
        elif args.command == "outline":
            result = outline(session_dir, under=args.under)
        elif args.command == "enter":
            result = enter(
                session_dir, node_id=args.id, position=args.position, under=args.under
            )
        elif args.command == "realise":
            result = realise(
                session_dir, node_id=args.id, line_start=args.line_start, line_end=args.line_end
            )
        elif args.command == "trail":
            result = trail(session_dir, limit=args.limit)
        elif args.command == "quiz-add":
            result = quiz_add(session_dir, questions=_read_json_file(args.file))
        elif args.command == "quiz-next":
            result = quiz_next(session_dir, count=args.count)
        elif args.command == "quiz-record":
            result = quiz_record(
                session_dir, question_id=args.question_id, verdict=args.verdict, note=args.note
            )
        elif args.command == "quiz-report":
            result = quiz_report(session_dir)
        elif args.command == "gaps-add":
            result = gaps_add(session_dir, gaps=_read_json_file(args.file))
        elif args.command == "gaps-list":
            result = gaps_list(session_dir)
        elif args.command == "describe":
            result = describe(
                session_dir,
                title=args.title,
                manual_section=args.manual_section,
                kind=args.kind,
                origin=args.origin,
                genre=args.genre,
                fidelity=args.fidelity,
            )
        else:
            result = status(session_dir)
    except ContractViolationError as exc:
        print(json.dumps({"error": str(exc), "kind": exc.kind}), file=sys.stderr)
        sys.exit(1)

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print(file=sys.stdout)


if __name__ == "__main__":
    main()
