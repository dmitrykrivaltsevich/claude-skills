#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Review state manager — CRUD operations for persistent consistency review state.

Manages a JSON state file that tracks the progress of a consistency review:
chunks (files), extracted claims, findings, and current phase.
Supports resume — re-initializing an existing review ID returns current state.

State location: ~/.cache/review-consistency/<review-id>.json  (overridable)

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
from contracts import ContractViolationError, precondition

# Default state directory — user-scoped cache.
_DEFAULT_STATE_DIR = Path.home() / ".cache" / "review-consistency"

# Valid review phases — ordered progression.
VALID_PHASES = ("inventory", "extract", "cross-check", "report")

# Valid chunk statuses.
VALID_CHUNK_STATUSES = ("unreviewed", "extracted", "reviewed")

# Valid finding statuses.
VALID_FINDING_STATUSES = ("open", "fixed", "wont-fix", "false-positive")

# Valid claim categories.
VALID_CLAIM_CATEGORIES = ("contract", "convention", "assertion", "reference")

# Valid finding severities — matches SKILL.md severity levels table.
VALID_SEVERITIES = ("critical", "major", "minor", "nit")

# Valid finding classes — the 8 inconsistency types from taxonomy.md.
VALID_FINDING_CLASSES = (
    "internal-contradiction",
    "forgotten-propagation",
    "semantic-drift",
    "stale-reference",
    "implausibility",
    "argument-incoherence",
    "convention-break",
    "incomplete-change",
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _state_path(review_id: str, state_dir: Path) -> Path:
    return state_dir / f"{review_id}.json"


def _load(review_id: str, state_dir: Path) -> dict:
    path = _state_path(review_id, state_dir)
    if not path.exists():
        raise FileNotFoundError(f"No review state found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _save(review_id: str, data: dict, state_dir: Path) -> None:
    path = _state_path(review_id, state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@precondition(
    lambda review_id, scope, **_: len(review_id.strip()) > 0,
    "review_id must be non-empty",
)
@precondition(
    lambda review_id, scope, **_: len(scope.strip()) > 0,
    "scope must be non-empty",
)
def init_review(
    review_id: str,
    scope: str,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Initialize a new review session, or resume an existing one."""
    path = _state_path(review_id, state_dir)
    if path.exists():
        data = _load(review_id, state_dir)
        return {
            "review_id": data["review_id"],
            "state_file": str(path),
            "resumed": True,
        }

    data = {
        "review_id": review_id,
        "scope": scope,
        "phase": "inventory",
        "chunks": [],
        "claims": [],
        "findings": [],
        "created_at": _now(),
        "updated_at": _now(),
    }
    _save(review_id, data, state_dir)
    return {
        "review_id": review_id,
        "state_file": str(path),
        "resumed": False,
    }


@precondition(
    lambda review_id, chunks, **_: len(chunks) > 0,
    "At least one chunk is required",
)
def add_chunks(
    review_id: str,
    chunks: list[dict],
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Add file chunks from inventory output. Deduplicates by path.

    If a chunk already exists with the same path:
    - Same hash → keep existing status (no change needed)
    - Different hash → update hash/size, reset status to 'unreviewed' (content changed)
    """
    data = _load(review_id, state_dir)
    existing_by_path: dict[str, int] = {}
    for i, c in enumerate(data["chunks"]):
        existing_by_path[c["path"]] = i

    next_id = len(data["chunks"]) + 1

    for chunk in chunks:
        path = chunk["path"]
        if path in existing_by_path:
            idx = existing_by_path[path]
            old = data["chunks"][idx]
            if old["hash"] != chunk["hash"]:
                # Content changed — update and reset status.
                old["hash"] = chunk["hash"]
                old["size"] = chunk["size"]
                old["status"] = "unreviewed"
        else:
            data["chunks"].append({
                "id": f"c{next_id}",
                "path": path,
                "size": chunk["size"],
                "hash": chunk["hash"],
                "status": "unreviewed",
            })
            existing_by_path[path] = len(data["chunks"]) - 1
            next_id += 1

    data["updated_at"] = _now()
    _save(review_id, data, state_dir)
    return {"total_chunks": len(data["chunks"])}


@precondition(
    lambda review_id, chunk_id, status, **_: status in VALID_CHUNK_STATUSES,
    f"status must be one of {VALID_CHUNK_STATUSES}",
)
def update_chunk(
    review_id: str,
    chunk_id: str,
    status: str,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Update the status of a specific chunk."""
    data = _load(review_id, state_dir)
    for c in data["chunks"]:
        if c["id"] == chunk_id:
            c["status"] = status
            data["updated_at"] = _now()
            _save(review_id, data, state_dir)
            return {"chunk_id": chunk_id, "status": status}

    raise ContractViolationError(
        f"Chunk not found: {chunk_id!r}", kind="precondition"
    )


@precondition(
    lambda review_id, claims, **_: len(claims) > 0,
    "At least one claim is required",
)
@precondition(
    lambda review_id, claims, **_: all(
        claim.get("category", "assertion") in VALID_CLAIM_CATEGORIES
        for claim in claims
    ),
    f"claim category must be one of {VALID_CLAIM_CATEGORIES}",
)
def add_claims(
    review_id: str,
    claims: list[dict],
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Add extracted claims for chunks."""
    data = _load(review_id, state_dir)
    next_id = len(data["claims"]) + 1

    for claim in claims:
        data["claims"].append({
            "id": f"cl{next_id}",
            "chunk_id": claim.get("chunk_id", ""),
            "text": claim.get("text", ""),
            "category": claim.get("category", "assertion"),
            "location": claim.get("location", ""),
        })
        next_id += 1

    data["updated_at"] = _now()
    _save(review_id, data, state_dir)
    return {"total_claims": len(data["claims"])}


@precondition(
    lambda review_id, findings, **_: len(findings) > 0,
    "At least one finding is required",
)
@precondition(
    lambda review_id, findings, **_: all(
        finding.get("severity", "major") in VALID_SEVERITIES
        for finding in findings
    ),
    f"finding severity must be one of {VALID_SEVERITIES}",
)
@precondition(
    lambda review_id, findings, **_: all(
        finding["class"] in VALID_FINDING_CLASSES
        for finding in findings
    ),
    f"finding class must be one of {VALID_FINDING_CLASSES}",
)
def add_findings(
    review_id: str,
    findings: list[dict],
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Add findings. Deduplicates by fingerprint — existing findings are not overwritten."""
    data = _load(review_id, state_dir)
    existing_fps = {f["fingerprint"] for f in data["findings"]}
    next_id = len(data["findings"]) + 1

    for finding in findings:
        fp = finding["fingerprint"]
        if fp in existing_fps:
            continue
        data["findings"].append({
            "id": f"f{next_id}",
            "fingerprint": fp,
            "class": finding["class"],
            "severity": finding.get("severity", "major"),
            "title": finding.get("title", ""),
            "where": finding.get("where", ""),
            "what": finding.get("what", ""),
            "why": finding.get("why", ""),
            "suggestion": finding.get("suggestion", ""),
            "status": "open",
            "chunk_ids": finding.get("chunk_ids", []),
            "claim_ids": finding.get("claim_ids", []),
        })
        existing_fps.add(fp)
        next_id += 1

    data["updated_at"] = _now()
    _save(review_id, data, state_dir)
    return {"total_findings": len(data["findings"])}


@precondition(
    lambda review_id, finding_id, status, **_: status in VALID_FINDING_STATUSES,
    f"status must be one of {VALID_FINDING_STATUSES}",
)
def update_finding(
    review_id: str,
    finding_id: str,
    status: str,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Update the status of a specific finding."""
    data = _load(review_id, state_dir)
    for f in data["findings"]:
        if f["id"] == finding_id:
            f["status"] = status
            data["updated_at"] = _now()
            _save(review_id, data, state_dir)
            return {"finding_id": finding_id, "status": status}

    raise ContractViolationError(
        f"Finding not found: {finding_id!r}", kind="precondition"
    )


def pending(
    review_id: str,
    limit: int | None = None,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Return chunks that still need work, ordered by status priority."""
    data = _load(review_id, state_dir)
    chunks = data.get("chunks", [])

    # unreviewed = all chunks not yet fully reviewed (need extraction or cross-check).
    unreviewed = [c for c in chunks if c["status"] in ("unreviewed", "extracted")]
    # unextracted = chunks with no claims extracted yet.
    unextracted = [c for c in chunks if c["status"] == "unreviewed"]
    extracted_not_reviewed = [c for c in chunks if c["status"] == "extracted"]

    # Priority: unextracted first (need claim extraction), then extracted (need cross-check).
    next_chunks = unextracted + extracted_not_reviewed
    if limit is not None:
        next_chunks = next_chunks[:limit]

    return {
        "unreviewed_chunks": len(unreviewed),
        "unextracted_chunks": len(unextracted),
        "extracted_not_reviewed": len(extracted_not_reviewed),
        "next_chunks": [{"id": c["id"], "path": c["path"]} for c in next_chunks],
    }


@precondition(
    lambda review_id, phase, **_: phase in VALID_PHASES,
    f"phase must be one of {VALID_PHASES}",
)
def update_phase(
    review_id: str,
    phase: str,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Update the current review phase."""
    data = _load(review_id, state_dir)
    data["phase"] = phase
    data["updated_at"] = _now()
    _save(review_id, data, state_dir)
    return {"phase": phase}


def get_status(
    review_id: str,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Return a summary of review progress."""
    data = _load(review_id, state_dir)
    chunks = data.get("chunks", [])
    findings = data.get("findings", [])
    return {
        "review_id": data["review_id"],
        "scope": data["scope"],
        "phase": data["phase"],
        "total_chunks": len(chunks),
        "extracted_chunks": sum(1 for c in chunks if c["status"] == "extracted"),
        "reviewed_chunks": sum(1 for c in chunks if c["status"] == "reviewed"),
        "unreviewed_chunks": sum(
            1 for c in chunks if c["status"] == "unreviewed"
        ),
        "total_claims": len(data.get("claims", [])),
        "total_findings": len(findings),
        "open_findings": sum(1 for f in findings if f["status"] == "open"),
        "fixed_findings": sum(1 for f in findings if f["status"] == "fixed"),
        "created_at": data.get("created_at", ""),
        "updated_at": data.get("updated_at", ""),
    }


def export_review(
    review_id: str,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Export the full review state."""
    return _load(review_id, state_dir)


def purge_stale_claims(
    review_id: str,
    state_dir: Path = _DEFAULT_STATE_DIR,
) -> dict:
    """Remove claims belonging to chunks that are in 'unreviewed' status.

    When a chunk's content changes (hash mismatch on re-add), its status
    resets to 'unreviewed'. Claims from the old content are stale and
    should be purged so re-extraction produces fresh claims.
    """
    data = _load(review_id, state_dir)
    unreviewed_ids = {c["id"] for c in data["chunks"] if c["status"] == "unreviewed"}
    before = len(data["claims"])
    data["claims"] = [
        cl for cl in data["claims"] if cl["chunk_id"] not in unreviewed_ids
    ]
    purged = before - len(data["claims"])
    data["updated_at"] = _now()
    _save(review_id, data, state_dir)
    return {"purged_claims": purged, "remaining_claims": len(data["claims"])}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _read_json_input(file_arg: str | None, inline_arg: str | None) -> list | dict:
    """Read JSON from --file path, stdin ('-'), or inline --arg string."""
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
    p.add_argument("--review-id", required=True)
    p.add_argument(
        "--state-dir", type=Path, default=_DEFAULT_STATE_DIR,
        help="Directory for state files.",
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entry point with subcommands for each operation."""
    parser = argparse.ArgumentParser(description="Review state manager.")
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init")
    _add_common_args(p_init)
    p_init.add_argument("--scope", required=True)

    # add-chunks
    p_ac = sub.add_parser("add-chunks")
    _add_common_args(p_ac)
    p_ac.add_argument("--chunks", default=None, help="JSON array string")
    p_ac.add_argument("--file", default=None, dest="chunks_file")

    # update-chunk
    p_uc = sub.add_parser("update-chunk")
    _add_common_args(p_uc)
    p_uc.add_argument("--chunk-id", required=True)
    p_uc.add_argument("--status", required=True)

    # add-claims
    p_acl = sub.add_parser("add-claims")
    _add_common_args(p_acl)
    p_acl.add_argument("--claims", default=None, help="JSON array string")
    p_acl.add_argument("--file", default=None, dest="claims_file")

    # add-findings
    p_af = sub.add_parser("add-findings")
    _add_common_args(p_af)
    p_af.add_argument("--findings", default=None, help="JSON array string")
    p_af.add_argument("--file", default=None, dest="findings_file")

    # update-finding
    p_uf = sub.add_parser("update-finding")
    _add_common_args(p_uf)
    p_uf.add_argument("--finding-id", required=True)
    p_uf.add_argument("--status", required=True)

    # pending
    p_pe = sub.add_parser("pending")
    _add_common_args(p_pe)
    p_pe.add_argument("--limit", type=int, default=None)

    # update-phase
    p_up = sub.add_parser("update-phase")
    _add_common_args(p_up)
    p_up.add_argument("--phase", required=True)

    # purge-stale-claims
    p_psc = sub.add_parser("purge-stale-claims")
    _add_common_args(p_psc)

    # status
    p_st = sub.add_parser("status")
    _add_common_args(p_st)

    # export
    p_ex = sub.add_parser("export")
    _add_common_args(p_ex)

    args = parser.parse_args(argv)
    state_dir = args.state_dir

    if args.command == "init":
        result = init_review(args.review_id, args.scope, state_dir=state_dir)
    elif args.command == "add-chunks":
        chunks = _read_json_input(args.chunks_file, args.chunks)
        result = add_chunks(args.review_id, chunks, state_dir=state_dir)
    elif args.command == "update-chunk":
        result = update_chunk(
            args.review_id, args.chunk_id, args.status, state_dir=state_dir
        )
    elif args.command == "add-claims":
        claims = _read_json_input(args.claims_file, args.claims)
        result = add_claims(args.review_id, claims, state_dir=state_dir)
    elif args.command == "add-findings":
        findings = _read_json_input(args.findings_file, args.findings)
        result = add_findings(args.review_id, findings, state_dir=state_dir)
    elif args.command == "update-finding":
        result = update_finding(
            args.review_id, args.finding_id, args.status, state_dir=state_dir
        )
    elif args.command == "pending":
        result = pending(args.review_id, limit=args.limit, state_dir=state_dir)
    elif args.command == "update-phase":
        result = update_phase(args.review_id, args.phase, state_dir=state_dir)
    elif args.command == "purge-stale-claims":
        result = purge_stale_claims(args.review_id, state_dir=state_dir)
    elif args.command == "status":
        result = get_status(args.review_id, state_dir=state_dir)
    elif args.command == "export":
        result = export_review(args.review_id, state_dir=state_dir)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
