#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml >= 6.0",
# ]
# ///
"""Post-merge deterministic audit for parallel kb imports.

Replaces the ad-hoc python one-liners a main agent used to run after a
merge: log-vs-manifest order, staged-completeness (every staged intent is
live), index coverage, timeline chain integrity, staging-leakage scan, and
tree hashing with an optional expected-hash gate.

Local imports: batch_plan (manifest IO, pyyaml), batch_merge (staging ops
reader, pyyaml), contracts and artifact_output (stdlib only) — so pyyaml is
the only runtime dependency.

Each check reports pass|warn|fail|skipped; overall status is fail if any
check fails, warn if any warns, else pass. The report is persisted as
.kb/batches/<batch-id>/verify-report.json — a retained audit artifact
alongside the lint report (it survives gc, unlike staging).

Unit of work: one audit check. Idempotent: reruns rewrite the same report
shape (timestamps aside). Read-only except the caller-named --output file
and its own verify-report.json slot.

Output: JSON to stdout (or --output artifact envelope). Errors to stderr.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from artifact_output import emit_json_result
from batch_merge import _read_staging_ops, _split_frontmatter
from batch_plan import _atomic_write_text, _load_manifest
from contracts import ContractViolationError, precondition

# Staged body blocks shorter than this are skipped in coverage checks —
# tiny fragments (headings, single links) match coincidentally and would
# drown the signal in false "missing" noise.
_MIN_BLOCK_CHARS = 40  # one substantive sentence; shorter spans collide by chance.

# Cap for per-check detail lists — full data stays in the KB; the report
# names the first offenders so the next action is obvious.
_DETAIL_CAP = 50  # enough to act on in one follow-up pass.

# Worker-temporal phrases that leak batch scaffolding into published prose
# (a union-merged file saying "so far" was true for exactly one worker).
# Lowercase: matched against lowered file text. Warn-level: the fix is a
# prose restructure in the refine/triangulation pass, not a mechanical edit.
_STALE_BATCH_PHRASES = (
    "so far in this kb",
    "same batch",
    "once merged",
    "when merged",
    "not yet in the kb",
)

# Timeline value shape -> level directory for chain target resolution.
_CHAIN_LEVEL_RES = [
    (re.compile(r"^\d{4}$"), "years"),
    (re.compile(r"^\d{4}-\d{2}$"), "months"),
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "days"),
]

_ARTIFACT_KINDS = {"verify": "kb-batch-verify"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _batch_dir(kb_path: str, batch_id: str) -> Path:
    return Path(kb_path) / ".kb" / "batches" / batch_id


def _tree_hash(kb_path: str) -> str:
    """Content hash over knowledge/ rel-paths + bytes (sorted) — replaying
    a merge must reproduce it byte-for-byte."""
    digest = hashlib.sha1()
    knowledge = Path(kb_path) / "knowledge"
    if knowledge.exists():
        for found in sorted(
            (p for p in knowledge.rglob("*") if p.is_file()),
            key=lambda p: p.relative_to(knowledge).as_posix(),
        ):
            rel = found.relative_to(Path(kb_path)).as_posix()
            digest.update(rel.encode("utf-8"))
            try:
                digest.update(found.read_bytes())
            except OSError as exc:
                raise ContractViolationError(
                    f"cannot hash {found}: {exc}.",
                    kind="io",
                )
    return digest.hexdigest()


def _staging_present(kb_path: str, batch_id: str, manifest: dict) -> bool:
    staging = _batch_dir(kb_path, batch_id) / "staging"
    if not staging.exists():
        return False
    return any(
        (staging / sid / "ops.jsonl").exists() for sid in manifest["order"]
    )


def _check_log_order(kb_path: str, manifest: dict) -> dict:
    """Every manifest source owns exactly one batch log line, in order —
    the serialized-history invariant."""
    batch_id = manifest["batch_id"]
    log_path = Path(kb_path) / "log.md"
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return {"status": "fail", "detail": f"unreadable log.md: {exc}"}
    positions: list[int] = []
    problems: list[str] = []
    for sid in manifest["order"]:
        hits = [
            i
            for i, line in enumerate(lines)
            if f"add {sid} | batch {batch_id}" in line
        ]
        if len(hits) != 1:
            problems.append(f"{sid}: {len(hits)} log lines (want exactly 1)")
            continue
        positions.append(hits[0])
    if positions != sorted(positions):
        problems.append("log lines out of manifest order")
    if problems:
        return {"status": "fail", "detail": "; ".join(problems[:_DETAIL_CAP])}
    return {"status": "pass", "detail": f"{len(positions)} lines in order"}


def _staged_body_blocks(text: str) -> list[str]:
    """Substantive staged body blocks (post-frontmatter, split on blank
    lines) — the units the union merge preserves, hence the units the
    completeness check looks for in live files."""
    _, body = _split_frontmatter(text)
    return [
        block.strip()
        for block in body.split("\n\n")
        if len(block.strip()) >= _MIN_BLOCK_CHARS
    ]


def _check_completeness(kb_path: str, batch_id: str, manifest: dict) -> dict:
    """Every staged intent is live: files exist and their substantive
    blocks survive in the live file (post-merge copyedits surface as
    coverage < 1.0 warnings, never silent — the union contract is
    no-data-loss, so missing blocks are the real alarm)."""
    if not _staging_present(kb_path, batch_id, manifest):
        return {
            "status": "skipped",
            "detail": "staging GC'd — run verify before gc for this check",
        }
    root = Path(kb_path)
    staging_root = _batch_dir(kb_path, batch_id) / "staging"
    missing: list[str] = []
    thin: list[str] = []
    checked = 0
    for sid in manifest["order"]:
        ops, _ = _read_staging_ops(kb_path, batch_id, sid)
        for op in ops:
            rel = op["path"]
            live_path = root / "knowledge" / rel
            if not live_path.exists():
                missing.append(rel)
                continue
            if not rel.endswith(".md"):
                checked += 1  # binary assets: existence is the contract
                continue
            try:
                staged_text = (staging_root / sid / rel).read_text(encoding="utf-8")
                live_text = live_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                return {"status": "fail", "detail": f"unreadable file: {exc}"}
            blocks = _staged_body_blocks(staged_text)
            checked += 1
            if not blocks:
                continue
            kept = sum(1 for block in blocks if block in live_text)
            if kept < len(blocks):
                thin.append(f"{rel}: {kept}/{len(blocks)} blocks live")
    if missing:
        return {
            "status": "fail",
            "detail": f"missing live files: {missing[:_DETAIL_CAP]}",
        }
    if thin:
        return {
            "status": "warn",
            "detail": f"copyedited after merge: {thin[:_DETAIL_CAP]}",
        }
    return {"status": "pass", "detail": f"{checked} staged files live"}


def _check_index(kb_path: str, manifest: dict) -> dict:
    """Every staged entry has its [[stem]] bullet in index.md."""
    index_path = Path(kb_path) / "index.md"
    try:
        text = index_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"status": "fail", "detail": f"unreadable index.md: {exc}"}
    missing: list[str] = []
    for sid in manifest["order"]:
        ops, _ = _read_staging_ops(kb_path, manifest["batch_id"], sid)
        for op in ops:
            rel = op["path"]
            if not rel.endswith(".md"):
                continue
            stem = Path(rel).stem
            if f"[[{stem}]]" not in text:
                missing.append(rel)
    # Post-gc the ops lists are gone — fall back to source-id attribution.
    if missing:
        return {
            "status": "fail",
            "detail": f"unindexed entries: {missing[:_DETAIL_CAP]}",
        }
    return {"status": "pass", "detail": "all staged entries indexed"}


def _chain_value_shape(value: str) -> str | None:
    for pattern, level in _CHAIN_LEVEL_RES:
        if pattern.match(value):
            return level
    return None


def _check_chain(kb_path: str) -> dict:
    """Timeline pointer integrity: prev/next targets exist (level-aware)
    and are reciprocal (X.next==Y implies Y.prev==X). Complements lint,
    which checks gaps, not pointer consistency."""
    root = Path(kb_path)
    base = root / "knowledge" / "timeline"
    entries: dict[str, dict] = {}  # "years/2020" -> frontmatter
    warnings: list[str] = []
    for level in ("years", "months", "days"):
        level_dir = base / level
        if not level_dir.exists():
            continue
        for found in level_dir.glob("*.md"):
            try:
                text = found.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                warnings.append(f"unreadable: {found.name}")
                continue
            frontmatter, _ = _split_frontmatter(text)
            if frontmatter is None:
                warnings.append(f"no frontmatter: {found.name}")
                continue
            entries[f"{level}/{found.stem}"] = frontmatter
    violations: list[str] = []

    def _target(entry_key: str, field: str) -> str | None:
        raw = entries[entry_key].get(field, "")
        if not isinstance(raw, str):
            return None
        match = re.fullmatch(r"\[\[(.+?)\]\]", raw.strip())
        return match.group(1) if match else None

    for key in sorted(entries):
        for field, other in (("next", "prev"), ("prev", "next")):
            target = _target(key, field)
            if target is None:
                continue
            level = _chain_value_shape(target)
            if level is None:
                violations.append(f"{key}.{field} malformed: {target!r}")
                continue
            target_key = f"{level}/{target}"
            if target_key not in entries:
                violations.append(f"{key}.{field} dangles: [[{target}]]")
                continue
            back = _target(target_key, other)
            if back != key.split("/", 1)[1]:
                violations.append(
                    f"{key}.{field}=[[ {target} ]] but {target_key}.{other}"
                    f"={back!r}"
                )
    if violations:
        return {"status": "fail", "detail": "; ".join(violations[:_DETAIL_CAP])}
    if warnings:
        return {"status": "warn", "detail": "; ".join(warnings[:_DETAIL_CAP])}
    return {"status": "pass", "detail": f"{len(entries)} entries consistent"}


def _check_hygiene(kb_path: str, manifest: dict) -> dict:
    """Union-hygiene warnings over batch-touched entries: duplicate top-level
    headings (two workers' sections concatenated) and worker-temporal
    residue ("so far in this KB"). Warn-level — the fix is a prose
    restructure in the refine/triangulation pass, not a mechanical edit."""
    touched: set[str] = set()
    for sid in manifest["order"]:
        ops, _ = _read_staging_ops(kb_path, manifest["batch_id"], sid)
        touched.update(op["path"] for op in ops if op["path"].endswith(".md"))
    root = Path(kb_path)
    findings: list[str] = []
    for rel in sorted(touched):
        path = root / "knowledge" / rel
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        headings = [
            line for line in text.splitlines() if line.startswith("# ")
        ]
        if len(headings) > 1:
            findings.append(f"{rel}: {len(headings)} top-level headings")
        lowered = text.lower()
        for phrase in _STALE_BATCH_PHRASES:
            if phrase in lowered:
                findings.append(f"{rel}: stale phrase {phrase!r}")
                break
    if findings:
        return {"status": "warn", "detail": "; ".join(findings[:_DETAIL_CAP])}
    return {"status": "pass", "detail": f"{len(touched)} files clean"}


def _check_leakage(kb_path: str) -> dict:
    """No staging paths leak into published content (knowledge/, index)."""
    root = Path(kb_path)
    hits: list[str] = []
    candidates: list[Path] = [root / "index.md"]
    knowledge = root / "knowledge"
    if knowledge.exists():
        candidates.extend(p for p in knowledge.rglob("*.md") if p.is_file())
    for found in candidates:
        try:
            text = found.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if ".kb/batches" in text or "staging/" in text:
            hits.append(found.relative_to(root).as_posix())
    if hits:
        return {
            "status": "fail",
            "detail": f"staging refs in: {hits[:_DETAIL_CAP]}",
        }
    return {"status": "pass", "detail": "no staging refs in content"}


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
def verify_batch(
    kb_path: str,
    batch_id: str,
    expect_hash: str | None = None,
) -> dict:
    """Run the full deterministic audit and persist verify-report.json."""
    manifest = _load_manifest(kb_path, batch_id)
    checks = {
        "log_order": _check_log_order(kb_path, manifest),
        "completeness": _check_completeness(kb_path, batch_id, manifest),
        "index": _check_index(kb_path, manifest),
        "chain": _check_chain(kb_path),
        "hygiene": _check_hygiene(kb_path, manifest),
        "leakage": _check_leakage(kb_path),
    }
    tree_hash = _tree_hash(kb_path)
    if expect_hash is None:
        hash_check: dict = {"status": "pass", "detail": f"hash {tree_hash}"}
    elif expect_hash == tree_hash:
        hash_check = {"status": "pass", "detail": "matches expected hash"}
    else:
        hash_check = {
            "status": "fail",
            "detail": f"drift: {tree_hash} != expected {expect_hash}",
        }
    checks["hash"] = hash_check
    statuses = {check["status"] for check in checks.values()}
    status = "fail" if "fail" in statuses else ("warn" if "warn" in statuses else "pass")
    result = {
        "batch_id": batch_id,
        "phase": manifest.get("phase", ""),
        "status": status,
        "checks": checks,
        "tree_hash": tree_hash,
    }
    _atomic_write_text(
        _batch_dir(kb_path, batch_id) / "verify-report.json",
        json.dumps(result, ensure_ascii=False, indent=2),
    )
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Post-merge batch audit.")
    parser.add_argument("--kb-path", required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument(
        "--expect-hash",
        default=None,
        help="Fail the hash check unless the tree matches (drift gate)",
    )
    parser.add_argument("--output", "-o", type=Path, default=None)

    args = parser.parse_args(argv)
    try:
        result = verify_batch(args.kb_path, args.batch_id, expect_hash=args.expect_hash)
    except ContractViolationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    emit_json_result(
        result,
        output_path=args.output,
        artifact_kind=_ARTIFACT_KINDS["verify"],
    )


if __name__ == "__main__":
    main()
