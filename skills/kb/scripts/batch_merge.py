#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml >= 6.0",
# ]
# ///
"""Batch reconciler — Reduce phase of parallel kb ingestion.

Replays staged worker proposals in manifest order (the linearization order),
fast-forwards non-overlapping changes mechanically, union-merges same-file
overlaps conservatively (never deletes another worker's facts; scalar
frontmatter conflicts are kept from the first writer and recorded for the
LLM refine pass), folds rule proposals, rebuilds the timeline chain,
appends index/log in order, and garbage-collects scratch state after a
self-verified clean lint.

Local imports: batch_plan (manifest IO + staging constants, pyyaml),
lint (self-check gate, stdlib only), contracts and artifact_output
(stdlib only) — so pyyaml is the only runtime dependency.

Unit of work: one staged file op. Checkpoint artifact: manifest cursor +
merge-queue.json. Resume path: re-run merge (idempotent; exact-sha1 and
post-union equality both skip). Handoff: {batch_id, applied, escalated}.

Output: JSON to stdout (or --output artifact envelope). Errors to stderr.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from artifact_output import emit_json_result
from batch_plan import (
    _allowed_staging_tops,
    _MAX_PROPOSAL_BYTES,
    _atomic_write_bytes,
    _atomic_write_text,
    _load_manifest,
)
from contracts import ContractViolationError, precondition
from lint import lint_kb

# Manifest phases this reconciler accepts. Merge persists "merging" at start
# and "linting" at end; replay from any of these is idempotent, so a crash
# resumes by simply re-running merge. Single-writer is assumed (the phase
# flag is a courtesy marker, not a lock) — never run two merges at once.
_MERGEABLE_PHASES = ("mapping", "merging", "linting")

# Timeline levels in chain order — each level links prev/next within itself
# and up to its parent (day→month→year). Fixed by the KB schema.
_TIMELINE_LEVELS = ("years", "months", "days")

# Expected stem shape per timeline level — parent links are derived only
# from valid stems so a stray file never gains a dangling [[..]] parent.
_TIMELINE_STEM_RES = {
    "years": re.compile(r"^\d{4}$"),
    "months": re.compile(r"^\d{4}-\d{2}$"),
    "days": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
}

# Category directory → index heading pattern (whole-word, case-insensitive).
# Covers every knowledge/ category created by init.py.
_INDEX_HEADING_RES = {
    "entities": re.compile(r"^#{1,6}\s+.*\bentit\w*\b.*$", re.IGNORECASE),
    "topics": re.compile(r"^#{1,6}\s+.*\btopics?\b.*$", re.IGNORECASE),
    "ideas": re.compile(r"^#{1,6}\s+.*\bideas?\b.*$", re.IGNORECASE),
    "locations": re.compile(r"^#{1,6}\s+.*\blocations?\b.*$", re.IGNORECASE),
    "sources": re.compile(r"^#{1,6}\s+.*\bsources?\b.*$", re.IGNORECASE),
    "citations": re.compile(r"^#{1,6}\s+.*\bcitations?\b.*$", re.IGNORECASE),
    "controversies": re.compile(
        r"^#{1,6}\s+.*\bcontrovers\w*\b.*$", re.IGNORECASE
    ),
    "meta": re.compile(r"^#{1,6}\s+.*\bmeta\b.*$", re.IGNORECASE),
    "questions": re.compile(r"^#{1,6}\s+.*\bquestions?\b.*$", re.IGNORECASE),
    "timeline": re.compile(r"^#{1,6}\s+.*\btimeline\b.*$", re.IGNORECASE),
}

# Cap for informational lists (external changes, unstaged files) — bounds
# result payloads on huge KBs while still naming the first offenders.
_INFO_LIST_CAP = 100  # enough to act on; full data stays on disk.

# Compact stdout envelopes for --output runs, keyed by subcommand — required
# by the artifact_output.emit_json_result contract (kind names the payload).
_ARTIFACT_KINDS = {
    "merge": "kb-batch-merge",
    "mark-done": "kb-batch-mark-done",
    "gc": "kb-batch-gc",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha1_text(text: str) -> str:
    """Sha1 of text (utf-8). Used by tests and merge-time dedup checks."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _batch_dir(kb_path: str, batch_id: str) -> Path:
    return Path(kb_path) / ".kb" / "batches" / batch_id


def _save_manifest(kb_path: str, batch_id: str, manifest: dict) -> None:
    manifest["updated_at"] = _utc_now()
    _atomic_write_text(
        _batch_dir(kb_path, batch_id) / "manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2),
    )


def _as_list(value) -> list:
    """Normalize a frontmatter scalar-or-list into a list — a bare
    `tags: ai` string must union as ["ai"], not ["a", "i"]."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _split_frontmatter(text: str) -> tuple[dict | None, str]:
    """Split (frontmatter dict|None, body). Unparseable YAML is treated as
    plain body — the merge must never lose content on a parse miss."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            raw = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :])
            try:
                parsed = yaml.safe_load(raw) or {}
            except yaml.YAMLError:
                return None, text
            if not isinstance(parsed, dict):
                return None, text
            return parsed, body
    return None, text


def _strip_fm_best_effort(text: str) -> str:
    """Remove a leading --- block without parsing it, so an unparseable
    staged file can still contribute its body without embedding a second
    frontmatter block into the merged file."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[index + 1 :])
    return text


def _render_frontmatter(frontmatter: dict) -> str:
    # Sorted keys keep merged output byte-deterministic across runs.
    return yaml.dump(frontmatter, default_flow_style=False, sort_keys=True).strip()


def _union_list(first: list, second: list) -> list:
    merged = list(first)
    for item in second:
        if item not in merged:
            merged.append(item)
    return merged


def _first_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            if title:
                return title
    return fallback


def _sans_updated(text: str) -> str:
    """Drop the `updated:` frontmatter line so convergence checks ignore the
    daily stamp — otherwise every replay rewrites and re-escalates."""
    return "\n".join(
        line for line in text.splitlines() if not line.startswith("updated:")
    )


def _is_empty_fm(value) -> bool:
    """Empty-equivalence for frontmatter scalars: None, "" and [] all mean
    "absent". Union and chain rebuild must treat them as identical, or
    replays flip-flop between spellings forever (real e2e finding)."""
    return value is None or value == "" or value == []


def _union_merge_md(
    accumulated: str | None, staged: str, staged_source: str
) -> tuple[str, bool, dict]:
    """Conservative union of two markdown proposals.

    Unions frontmatter source-ids/tags, keeps every body fact from both
    sides. Scalar frontmatter conflicts keep the first writer's value and
    are recorded (never silently dropped) for the LLM refine pass.
    Returns (merged_text, overlap, conflicts).
    """
    if accumulated is None:
        return staged, False, {}
    if sha1_text(accumulated) == sha1_text(staged):
        return accumulated, False, {}
    acc_fm, acc_body = _split_frontmatter(accumulated)
    stg_fm, stg_body = _split_frontmatter(staged)
    if acc_fm is None:
        # Accumulated side is plain text — append staged body (delimiters
        # stripped best-effort) only when it adds new content.
        candidate = _strip_fm_best_effort(staged).strip()
        if candidate and candidate not in acc_body:
            return accumulated.rstrip() + "\n\n" + candidate + "\n", True, {}
        return accumulated, True, {}
    if stg_fm is None:
        candidate = _strip_fm_best_effort(staged).strip()
        if candidate and candidate not in acc_body:
            return (
                accumulated.rstrip()
                + "\n\n<!-- staged variant with unparseable frontmatter from "
                + staged_source
                + " -->\n\n"
                + candidate
                + "\n",
                True,
                {"frontmatter": ["unparseable-staged"]},
            )
        return accumulated, True, {"frontmatter": ["unparseable-staged"]}
    merged_fm = dict(acc_fm)
    conflicts: dict[str, list] = {}
    for key, value in stg_fm.items():
        if key in ("source-ids", "tags"):
            merged_fm[key] = _union_list(
                _as_list(acc_fm.get(key)), _as_list(value)
            )
        elif key == "updated":
            merged_fm[key] = _utc_today()
        elif key not in merged_fm or merged_fm[key] is None:
            # Backfill only truly absent data (missing key or YAML null).
            # An explicit "" / [] is settled information ("known empty",
            # e.g. chain-managed prev/next) — adopting a staged guess over
            # it would ping-pong against the chain rebuild every replay.
            if value is not None:
                merged_fm[key] = value
        elif (
            not _is_empty_fm(merged_fm[key])
            and not _is_empty_fm(value)
            and merged_fm[key] != value
        ):
            # First writer wins for scalars; the staged value is recorded
            # for the LLM refine pass instead of being silently lost.
            # Empty-vs-empty ("" vs null) keeps accumulated VERBATIM —
            # adopting the other spelling would ping-pong every replay.
            conflicts[key] = [merged_fm[key], value]
    if staged_source not in _as_list(merged_fm.get("source-ids")):
        merged_fm["source-ids"] = _union_list(
            _as_list(merged_fm.get("source-ids")), [staged_source]
        )
    # Idea entries require attributable fields — backfill from staged when
    # the accumulated side lacks them so the merge never invalidates one.
    if merged_fm.get("type") == "idea":
        for key in ("idea-kind", "attributed-to", "year"):
            if _is_empty_fm(merged_fm.get(key)):
                staged_value = stg_fm.get(key)
                if not _is_empty_fm(staged_value):
                    merged_fm[key] = staged_value
    merged_fm["updated"] = _utc_today()
    merged_body = acc_body
    stripped = stg_body.strip()
    if stripped and stripped not in acc_body:
        merged_body = acc_body.rstrip() + "\n\n" + stripped + "\n"
    # Normalized trailing newline: _split_frontmatter's line-join drops it,
    # so without this every re-union would differ by one byte forever.
    merged_body = merged_body.strip() + "\n"
    return (
        "---\n" + _render_frontmatter(merged_fm) + "\n---\n\n" + merged_body,
        True,
        conflicts,
    )


def _check_rel(
    kb_path: str, rel: str, source_id: str, extra_tops: list[str] | tuple[str, ...] = ()
) -> None:
    """Validate a staged rel path (ops records may be hand-written, so the
    stage_write precondition cannot be the only gate). Mirrors the staging
    contract: knowledge-mirror only, .md outside assets/, assets namespaced
    per source. The admitted set is built-ins ∪ live tree ∪ the batch
    manifest's declared tops (tolerates pre-feature manifests without the
    key)."""
    allowed = _allowed_staging_tops(kb_path, extra_tops)
    parts = Path(rel).parts
    if (
        not rel
        or not parts
        or rel.startswith("/")
        or ".." in parts
        or parts[0] not in allowed
    ):
        raise ContractViolationError(
            f"staged path {rel!r} escapes the knowledge mirror. Restage via "
            "stage_write.",
            kind="precondition",
        )
    name = parts[-1]
    if not name or name.startswith("."):
        raise ContractViolationError(
            f"staged path {rel!r} is not a valid entry name.",
            kind="precondition",
        )
    if parts[0] != "assets" and not name.endswith(".md"):
        raise ContractViolationError(
            f"staged path {rel!r} must be markdown outside assets/.",
            kind="precondition",
        )
    if parts[0] == "assets" and (len(parts) < 3 or parts[1] != source_id):
        raise ContractViolationError(
            f"assets must be namespaced per source "
            f"(assets/{source_id}/...), got {rel!r}.",
            kind="precondition",
        )


def _resolve_live(kb_path: str, rel: str) -> Path:
    """Resolve a knowledge-relative path and confine it inside knowledge/.

    Staging inputs are worker-controlled, so every merge-side path proves
    confinement (mirrors batch_plan._confine at the other trust boundary).
    """
    root = Path(kb_path).resolve()
    knowledge = root / "knowledge"
    target = knowledge / rel
    try:
        resolved = target.resolve()
    except OSError as exc:
        raise ContractViolationError(
            f"cannot resolve live path for {rel!r}: {exc}.",
            kind="io",
        )
    base = knowledge.resolve() if knowledge.exists() else knowledge
    if resolved != base and base not in resolved.parents:
        raise ContractViolationError(
            f"refusing to touch {rel!r}: escapes knowledge/.",
            kind="invariant",
        )
    return target


def _read_staged(staging_root: Path, source_id: str, rel: str) -> bytes:
    """Read a staged file, refusing symlinks (a planted link would pull
    outside content into the KB on merge)."""
    staged_file = staging_root / source_id / rel
    if staged_file.is_symlink():
        raise ContractViolationError(
            f"refusing to merge symlinked staged file: {staged_file}. "
            "Replace it with a real file and restage.",
            kind="invariant",
        )
    try:
        return staged_file.read_bytes()
    except OSError as exc:
        raise ContractViolationError(
            f"staged file missing: {staged_file}: {exc}. The worker must "
            f"restage {rel} for {source_id}.",
            kind="io",
        )


def _read_staging_ops(
    kb_path: str, batch_id: str, source_id: str
) -> tuple[list[dict], int]:
    """Read one source's ops.jsonl, keeping the last record per path so a
    worker re-staging the same file collapses to its final version.
    Returns (ops, superseded_count). Corrupt lines raise explicitly."""
    ops_path = (
        _batch_dir(kb_path, batch_id) / "staging" / source_id / "ops.jsonl"
    )
    if not ops_path.exists():
        return [], 0
    try:
        lines = ops_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ContractViolationError(
            f"cannot read staging ops {ops_path}: {exc}.",
            kind="io",
        )
    total = sum(1 for line in lines if line.strip())
    latest: dict[str, dict] = {}
    order: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ContractViolationError(
                f"corrupt ops line in {ops_path}: {exc}. The worker must "
                f"restage {source_id}'s files.",
                kind="io",
            )
        if not isinstance(record, dict) or not isinstance(
            record.get("path"), str
        ) or not isinstance(record.get("staged_sha1"), str):
            raise ContractViolationError(
                f"corrupt ops record in {ops_path} (missing path/staged_sha1)."
                f" The worker must restage {source_id}'s files.",
                kind="io",
            )
        # Last-occurrence order: a restaged path takes the position of its
        # latest write, so intra-source restage order decides first-writer.
        latest[record["path"]] = record
        if record["path"] in order:
            order.remove(record["path"])
        order.append(record["path"])
    return [latest[path] for path in order], total - len(latest)


def _live_snapshot_files(root: Path) -> list[Path]:
    """Live files covered by plan/merge snapshots: every knowledge markdown
    entry plus every asset blob (binaries change too, and must be visible
    to external-change detection)."""
    knowledge = root / "knowledge"
    if not knowledge.exists():
        return []
    files = list(knowledge.rglob("*.md"))
    assets = knowledge / "assets"
    if assets.exists():
        files.extend(
            p for p in assets.rglob("*") if p.is_file() and not p.is_symlink()
        )
    return files


def _ops_fingerprint(ops: list[dict]) -> str:
    """Stable hash of one source's staged ops (detects restage-after-merge)."""
    return hashlib.sha1(
        json.dumps(ops, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _detect_external_changes(kb_path: str, manifest: dict) -> dict:
    """Diff live knowledge files against the plan-time snapshot so the
    result reports what moved under the batch (informational only — merge
    still proceeds; per-file MVCC decides fast-forward vs escalate)."""
    root = Path(kb_path)
    base: dict = manifest.get("base", {})
    current: dict[str, str] = {}
    unreadable: list[str] = []
    for found in _live_snapshot_files(root):
        rel = found.relative_to(root).as_posix()
        try:
            current[rel] = _sha1_bytes(found.read_bytes())
        except OSError:
            unreadable.append(rel)
    for top in ("index.md", "log.md"):
        candidate = root / top
        if candidate.exists():
            try:
                current[top] = _sha1_bytes(candidate.read_bytes())
            except OSError:
                unreadable.append(top)
    changed = sorted(
        rel
        for rel, sha in current.items()
        if rel in base and base[rel] != sha
    )
    added = sorted(rel for rel in current if rel not in base)
    deleted = sorted(rel for rel in base if rel not in current)
    return {
        "changed": changed[:_INFO_LIST_CAP],
        "added": added[:_INFO_LIST_CAP],
        "deleted": deleted[:_INFO_LIST_CAP],
        "unreadable": unreadable[:_INFO_LIST_CAP],
    }


def _find_unstaged_files(kb_path: str, batch_id: str, manifest: dict) -> list[str]:
    """List staged files with no ops.jsonl record (worker crashed between
    write and record, or bypassed stage_write). Warning only, capped."""
    staging_root = _batch_dir(kb_path, batch_id) / "staging"
    referenced: set[str] = set()
    for source_id in manifest["order"]:
        ops, _ = _read_staging_ops(kb_path, batch_id, source_id)
        referenced.update(f"{source_id}/{op['path']}" for op in ops)
        ops_path = staging_root / source_id / "ops.jsonl"
        if ops_path.exists():
            referenced.add(f"{source_id}/ops.jsonl")
        proposals = staging_root / source_id / "rules-proposals.md"
        if proposals.exists():
            referenced.add(f"{source_id}/rules-proposals.md")
    unstaged: list[str] = []
    if staging_root.exists():
        for found in sorted(staging_root.rglob("*")):
            if not found.is_file():
                continue
            rel = found.relative_to(staging_root).as_posix()
            if rel not in referenced:
                # Symlinks are flagged, not followed — a planted link must
                # be visible, never silently merged.
                unstaged.append(rel + (" [symlink]" if found.is_symlink() else ""))
    return unstaged[:_INFO_LIST_CAP]


def _append_log(kb_path: str, batch_id: str, applied_sources: list[str]) -> None:
    """Append one log line per applied source, in manifest order — the same
    `add <id>` shape sequential kb:add produces (plus an intentional
    `| batch <id>` suffix marking batch provenance), so history stays
    linear. Idempotent: existing batch lines for a source are never
    duplicated, which keeps crash-replay safe."""
    if not applied_sources:
        return
    log_path = Path(kb_path) / "log.md"
    try:
        existing = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    except OSError as exc:
        raise ContractViolationError(
            f"cannot read {log_path}: {exc}.",
            kind="io",
        )
    today = _utc_today()
    lines = "".join(
        f"{today} add {sid} | batch {batch_id}\n"
        for sid in applied_sources
        if f"add {sid} | batch {batch_id}" not in existing
    )
    if not lines:
        return
    try:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(lines)
    except OSError as exc:
        raise ContractViolationError(
            f"cannot append {log_path}: {exc}. Check disk space.",
            kind="io",
        )


def _ensure_index_bullet(
    kb_path: str, batch_id: str, rel: str, title: str, source_id: str
) -> None:
    """Crash-window repair: if a replay skips an already-merged file, its
    index bullet may still be missing (bullet appends happen after file
    writes). Reconciles exactly one bullet, idempotently."""
    index_path = Path(kb_path) / "index.md"
    try:
        text = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    except OSError as exc:
        raise ContractViolationError(
            f"cannot read {index_path}: {exc}.",
            kind="io",
        )
    if f"[[{Path(rel).stem}]]" in text and f"(batch {batch_id})" in text:
        return
    _append_index(kb_path, batch_id, [(rel, source_id, title)])


def _append_index(
    kb_path: str, batch_id: str, created: list[tuple[str, str, str]]
) -> None:
    """Insert index bullets for newly created entries at the end of their
    category section (in apply order), creating the heading if absent.
    Existing bullets are never duplicated — replays are no-ops."""
    if not created:
        return
    index_path = Path(kb_path) / "index.md"
    try:
        text = index_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractViolationError(
            f"cannot read {index_path}: {exc}.",
            kind="io",
        )
    lines = text.splitlines()
    existing = set(lines)
    by_category: dict[str, list[tuple[str, str, str]]] = {}
    for rel, sid, title in created:
        category = rel.split("/", 1)[0]
        bullet = f"- [[{Path(rel).stem}]] — {title} (batch {batch_id})"
        if bullet in existing:
            continue
        by_category.setdefault(category, []).append((rel, sid, title))
    for category, items in by_category.items():
        pattern = _INDEX_HEADING_RES.get(category)
        heading_idx = None
        if pattern is not None:
            for pos, line in enumerate(lines):
                if pattern.match(line):
                    heading_idx = pos
                    break
        bullets = [
            f"- [[{Path(rel).stem}]] — {title} (batch {batch_id})"
            for rel, _, title in items
        ]
        if heading_idx is None:
            lines.extend(["", f"## {category.capitalize()}", "", *bullets])
        else:
            # Insert at the end of the section (before the next heading).
            end = heading_idx + 1
            while end < len(lines) and not lines[end].lstrip().startswith("#"):
                end += 1
            lines[end:end] = [*bullets]
    _atomic_write_text(index_path, "\n".join(lines) + "\n")


@precondition(
    lambda kb_path, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
def rebuild_timeline_chain(
    kb_path: str, only: set[str] | None = None
) -> dict:
    """Normalize prev/next/parent links across timeline entries.

    Content stays worker-owned; only chain pointers are rewritten, in sorted
    stem order, so concurrent date insertions converge deterministically.
    With only={knowledge-relative rels}, rewrites just those files plus
    their immediate chain neighbors (whose pointers the insertion shifts).
    Stems that do not look like dates are left alone, and no empty parent
    key is ever added.
    """
    root = Path(kb_path)
    updated = 0
    for level in _TIMELINE_LEVELS:
        level_dir = root / "knowledge" / "timeline" / level
        if not level_dir.exists():
            continue
        stem_re = _TIMELINE_STEM_RES[level]
        stems = sorted(
            p.stem for p in level_dir.glob("*.md") if stem_re.match(p.stem)
        )
        if only is not None:
            wanted = {
                Path(rel).stem
                for rel in only
                if rel.startswith(f"timeline/{level}/")
            }
            if not wanted:
                continue
            # Insertion shifts neighbors' pointers — include them.
            targets: set[str] = set()
            for stem in wanted:
                if stem not in stems:
                    continue
                pos = stems.index(stem)
                targets.add(stem)
                if pos > 0:
                    targets.add(stems[pos - 1])
                if pos + 1 < len(stems):
                    targets.add(stems[pos + 1])
        else:
            targets = set(stems)
        for pos, stem in enumerate(stems):
            if stem not in targets:
                continue
            path = level_dir / f"{stem}.md"
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            frontmatter, body = _split_frontmatter(text)
            if frontmatter is None:
                continue  # no parseable frontmatter — leave content alone.
            prev = f"[[{stems[pos - 1]}]]" if pos > 0 else ""
            nxt = f"[[{stems[pos + 1]}]]" if pos + 1 < len(stems) else ""
            parent = ""
            if level == "months":
                parent = f"[[{stem[:4]}]]"
            elif level == "days":
                parent = f"[[{stem[:7]}]]"
            changed = False
            # The chain is authoritative for prev/next: always write the
            # computed value (this also normalizes worker-guessed links and
            # null spellings in one pass; afterwards replays are stable).
            for key, value in (("prev", prev), ("next", nxt)):
                if frontmatter.get(key) != value:
                    frontmatter[key] = value
                    changed = True
            if parent:
                if frontmatter.get("parent") != parent:
                    frontmatter["parent"] = parent
                    changed = True
            # A missing/empty parent on year entries (or any file that never
            # had one) is left absent — never write an empty parent key.
            if changed:
                frontmatter["updated"] = _utc_today()
                merged = (
                    "---\n"
                    + _render_frontmatter(frontmatter)
                    + "\n---\n\n"
                    + body.strip()
                    + "\n"
                )
                _atomic_write_text(path, merged)
                updated += 1
    return {"updated": updated}


@precondition(
    lambda kb_path, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
@precondition(
    lambda batch_id, **_: len(batch_id.strip()) > 0,
    "batch_id must be non-empty",
)
def fold_rules_proposals(kb_path: str, batch_id: str) -> dict:
    """Fold per-worker rules-proposals.md into one combined file.

    Accepts -, * and + bullets; identical bullets dedup globally with first
    source keeping attribution. Oversized or undecodable files raise
    explicitly (a proposal file is bullets, not a dump). Idempotent.
    """
    staging_root = _batch_dir(kb_path, batch_id) / "staging"
    manifest = _load_manifest(kb_path, batch_id)
    seen: set[str] = set()
    skipped_symlinks: list[str] = []
    sections: list[str] = []
    for source_id in manifest["order"]:
        proposal_path = staging_root / source_id / "rules-proposals.md"
        if not proposal_path.exists():
            continue
        if proposal_path.is_symlink():
            # Reported, never followed — same rule as staged content.
            skipped_symlinks.append(f"{source_id}/rules-proposals.md")
            continue
        try:
            data = proposal_path.read_bytes()
        except OSError as exc:
            raise ContractViolationError(
                f"cannot read {proposal_path}: {exc}.",
                kind="io",
            )
        if len(data) > _MAX_PROPOSAL_BYTES:
            raise ContractViolationError(
                f"rules proposal {proposal_path} exceeds "
                f"{_MAX_PROPOSAL_BYTES} bytes — proposals are bullets "
                "with evidence quotes, not extraction dumps. Trim it.",
                kind="precondition",
            )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ContractViolationError(
                f"rules proposal {proposal_path} is not valid utf-8: {exc}.",
                kind="precondition",
            )
        fresh = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped[0] not in "-*+":
                continue
            if stripped not in seen:
                seen.add(stripped)
                fresh.append(stripped)
        if fresh:
            sections.append(f"## {source_id}\n\n" + "\n".join(fresh))
    body = (
        f"# Batch {batch_id} — rule proposals\n\n"
        + ("\n\n".join(sections) if sections else "_No proposals in this batch._")
        + "\n"
    )
    combined = _batch_dir(kb_path, batch_id) / "rules-combined.md"
    _atomic_write_text(combined, body)
    return {
        "proposals": len(seen),
        "path": str(combined),
        "skipped_symlinks": skipped_symlinks,
    }


@precondition(
    lambda kb_path, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
@precondition(
    lambda batch_id, **_: len(batch_id.strip()) > 0,
    "batch_id must be non-empty",
)
def merge_batch(kb_path: str, batch_id: str, dry_run: bool = False) -> dict:
    """Replay staged ops in manifest order with MVCC fast-forward checks.

    Idempotent: re-runs skip byte-identical files (exact-sha1) and converged
    unions (post-union equality), so a crash resumes by re-running merge and
    log/index appends never duplicate. dry_run computes counts and writes
    nothing (no manifest, queue, index, log, or knowledge changes).
    """
    manifest = _load_manifest(kb_path, batch_id)
    if manifest.get("phase") not in _MERGEABLE_PHASES:
        raise ContractViolationError(
            f"batch {batch_id!r} is in phase {manifest.get('phase')!r}; "
            f"merge needs one of {_MERGEABLE_PHASES}. Check batch status.",
            kind="precondition",
        )
    per_source_ops: list[tuple[str, list[dict]]] = []
    all_source_ops: list[tuple[str, list[dict]]] = []
    superseded = 0
    for sid in manifest["order"]:
        ops, dropped = _read_staging_ops(kb_path, batch_id, sid)
        all_source_ops.append((sid, ops))
        superseded += dropped
    total_ops = sum(len(ops) for _, ops in all_source_ops)
    # Per-wave materialization cursor: {source_id: ops-sha} for already
    # merged staging. Absent on pre-cursor manifests — treated as nothing
    # merged yet, so one replay converges them onto the cursor.
    merged: dict[str, str] = dict(manifest.get("merged", {}))
    if total_ops == 0 and not merged and not dry_run:
        raise ContractViolationError(
            f"batch {batch_id!r} has no staged proposals yet. Workers must "
            "run stage-write first — merging an empty batch would falsely "
            "advance the phase.",
            kind="precondition",
        )
    # Replay only sources with new or changed staging since their last
    # merge. Empty-ops sources (future waves not yet staged) are skipped
    # without being recorded as merged.
    per_source_ops = [
        (sid, ops)
        for sid, ops in all_source_ops
        if ops and _ops_fingerprint(ops) != merged.get(sid)
    ]
    external_changes = _detect_external_changes(kb_path, manifest)
    unstaged_files = [] if dry_run else _find_unstaged_files(
        kb_path, batch_id, manifest
    )

    # Persist "merging" first so a crash mid-run resumes explicitly from it.
    if not dry_run and manifest.get("phase") != "merging":
        manifest["phase"] = "merging"
        _save_manifest(kb_path, batch_id, manifest)

    root = Path(kb_path)
    staging_root = _batch_dir(kb_path, batch_id) / "staging"
    applied = 0
    skipped = 0
    escalated = 0
    created: list[tuple[str, str, str]] = []
    touched_timeline: set[str] = set()
    queue_entries: list[dict] = []
    # In-memory view of files created/merged during this run (bytes) plus
    # which source last wrote each path, so later sources in the same replay
    # merge against accumulated state with full contributor tracking.
    accumulated: dict[str, bytes] = {}
    accumulated_source: dict[str, str] = {}

    for source_id, ops in per_source_ops:
        for op in ops:
            rel: str = op["path"]
            _check_rel(kb_path, rel, source_id, manifest.get("allowed_tops", []))
            staged_bytes = _read_staged(staging_root, source_id, rel)
            live_path = _resolve_live(kb_path, rel)
            base_sha1: str = op.get("base_sha1", "")
            staged_sha1 = _sha1_bytes(staged_bytes)
            if staged_sha1 != op.get("staged_sha1"):
                # The staged file changed after its ops record was written
                # (hand edit or partial restage) — never apply blind.
                raise ContractViolationError(
                    f"staged file {rel} for {source_id} no longer matches "
                    "its ops record. Restage it via stage_write, then "
                    "re-run merge.",
                    kind="invariant",
                )
            if rel in accumulated:
                live_bytes: bytes | None = accumulated[rel]
            elif live_path.exists():
                if live_path.is_symlink():
                    raise ContractViolationError(
                        f"refusing to merge through symlinked live file: "
                        f"{live_path}. Replace it with a real file.",
                        kind="invariant",
                    )
                try:
                    live_bytes = live_path.read_bytes()
                except OSError as exc:
                    raise ContractViolationError(
                        f"cannot read live file {live_path}: {exc}. Fix or "
                        "remove it, then re-run merge.",
                        kind="io",
                    )
            else:
                live_bytes = None
            if live_bytes is not None and _sha1_bytes(live_bytes) == staged_sha1:
                skipped += 1  # exact match — already applied, nothing to do.
                continue
            if live_bytes is None:
                if not dry_run:
                    live_path.parent.mkdir(parents=True, exist_ok=True)
                    _atomic_write_bytes(live_path, staged_bytes)
                accumulated[rel] = staged_bytes
                accumulated_source[rel] = source_id
                applied += 1
                if rel.endswith(".md"):
                    try:
                        title = _first_title(
                            staged_bytes.decode("utf-8"), Path(rel).stem
                        )
                    except UnicodeDecodeError as exc:
                        raise ContractViolationError(
                            f"staged file {staged_file} is not valid utf-8: "
                            f"{exc}. Stage text as .md or binary under "
                            "assets/.",
                            kind="precondition",
                        )
                    created.append((rel, source_id, title))
                if rel.startswith("timeline/"):
                    touched_timeline.add(rel)
                continue
            live_sha1 = _sha1_bytes(live_bytes)
            if live_sha1 == base_sha1:
                # Untouched since the worker staged — fast-forward.
                if not dry_run:
                    _atomic_write_bytes(live_path, staged_bytes)
                accumulated[rel] = staged_bytes
                accumulated_source[rel] = source_id
                applied += 1
                continue
            # Overlap: the file moved under the staged proposal.
            if rel.endswith(".md"):
                try:
                    live_text = live_bytes.decode("utf-8")
                    staged_text = staged_bytes.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise ContractViolationError(
                        f"cannot merge {rel} as text: {exc}. Stage binaries "
                        "under assets/.",
                        kind="precondition",
                    )
                merged_text, _, conflicts = _union_merge_md(
                    live_text, staged_text, source_id
                )
                if _sans_updated(merged_text) == _sans_updated(live_text):
                    # Union converged modulo the updated stamp — a replay
                    # (even days later) must not rewrite or re-escalate.
                    skipped += 1
                    continue
                if not dry_run:
                    _atomic_write_text(live_path, merged_text)
                accumulated[rel] = merged_text.encode("utf-8")
                first = accumulated_source.get(rel, base_sha1[:8] or "live")
                parties = [first] if first == source_id else [first, source_id]
                accumulated_source[rel] = source_id
                queue_entries.append(
                    {
                        "path": rel,
                        "status": "done-mechanical",
                        "parties": parties,
                        "needs_llm": True,
                        "conflicts": conflicts,
                    }
                )
                if rel.startswith("timeline/"):
                    touched_timeline.add(rel)
            else:
                # Binary asset collision — keep both variants, never overwrite.
                # The variant name is content-derived, so replays converge.
                stem = live_path.stem
                variant = live_path.with_name(
                    f"{stem}-{staged_sha1[:8]}{live_path.suffix or '.bin'}"
                )
                if variant.exists():
                    try:
                        if _sha1_bytes(variant.read_bytes()) == staged_sha1:
                            skipped += 1
                            continue
                    except OSError as exc:
                        raise ContractViolationError(
                            f"cannot read asset variant {variant}: {exc}.",
                            kind="io",
                        )
                if not dry_run:
                    _atomic_write_bytes(variant, staged_bytes)
                queue_entries.append(
                    {
                        "path": rel,
                        "status": "done-mechanical-variant",
                        "parties": [accumulated_source.get(rel, "live"), source_id],
                        "needs_llm": False,
                        "conflicts": {},
                        "variant": variant.name,
                    }
                )
            escalated += 1
            applied += 1

    # Batch-owned paths are not "external", even though they differ from the
    # plan-time snapshot on replay — without this, every replay would report
    # its own outputs as external changes. Owned covers ALL staged sources
    # (not just this run's replay set) so earlier waves' merged files are
    # not misreported as external in later wave merges.
    owned = {f"knowledge/{op['path']}" for _, ops in all_source_ops for op in ops}
    for bucket in ("changed", "added", "deleted"):
        external_changes[bucket] = [
            rel for rel in external_changes[bucket] if rel not in owned
        ]
    # External date edits shift chain pointers too — fold them into the
    # scoped timeline rebuild.
    for rel in (
        external_changes["changed"]
        + external_changes["added"]
        + external_changes["deleted"]
    ):
        if rel.startswith("knowledge/timeline/"):
            touched_timeline.add(rel[len("knowledge/") :])

    if not dry_run:
        queue_path = _batch_dir(kb_path, batch_id) / "merge-queue.json"
        # Preserve earlier escalations still awaiting LLM refine: a clean
        # replay must not erase the audit of a genuine overlap. New
        # entries for the same path supersede (fresher conflict data).
        previous: dict[str, dict] = {}
        if queue_path.exists():
            try:
                previous = {
                    e["path"]: e
                    for e in json.loads(
                        queue_path.read_text(encoding="utf-8")
                    ).get("entries", [])
                    if isinstance(e, dict) and isinstance(e.get("path"), str)
                }
            except (OSError, json.JSONDecodeError):
                previous = {}
        for entry in queue_entries:
            previous[entry["path"]] = entry
        _atomic_write_text(
            queue_path,
            json.dumps(
                {"batch_id": batch_id, "entries": list(previous.values())},
                ensure_ascii=False,
                indent=2,
            ),
        )
        # Crash-window repair: log/index appends happen after file writes,
        # so a crash between them leaves applied files without provenance.
        # _append_log is idempotent and bullets are reconciled per file —
        # replays therefore heal instead of duplicating.
        _append_log(
            kb_path,
            batch_id,
            [sid for sid, ops in per_source_ops if ops],
        )
        _append_index(kb_path, batch_id, created)
        for sid, ops in per_source_ops:
            for op in ops:
                rel = op["path"]
                if not rel.endswith(".md"):
                    continue
                live_path = root / "knowledge" / rel
                if not live_path.exists():
                    continue
                try:
                    live_text = live_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                _ensure_index_bullet(
                    kb_path,
                    batch_id,
                    rel,
                    _first_title(live_text, Path(rel).stem),
                    sid,
                )
        rebuild_timeline_chain(kb_path, only=touched_timeline or None)
        fold_rules_proposals(kb_path, batch_id)
        for sid, ops in per_source_ops:
            if ops:
                merged[sid] = _ops_fingerprint(ops)
        manifest["merged"] = merged
        # Flip to linting only when every source has merged at least once;
        # intermediate wave merges keep mapping/merging so later waves can
        # still stage (stage_write has no phase gate; merge accepts both).
        # A source that never stages anything blocks the flip — every
        # source must stage at least its analysis entry.
        if all(sid in merged for sid in manifest["order"]):
            manifest["phase"] = "linting"
        manifest["cursor"] = {
            "applied_total": manifest.get("cursor", {}).get("applied_total", 0)
            + applied,
        }
        _save_manifest(kb_path, batch_id, manifest)
    return {
        "batch_id": batch_id,
        "applied": applied,
        "skipped_dedup": skipped,
        "superseded": superseded,
        "escalated": escalated,
        "external_changes": external_changes,
        "unstaged_files": unstaged_files,
        "dry_run": dry_run,
    }


@precondition(
    lambda kb_path, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
@precondition(
    lambda batch_id, **_: len(batch_id.strip()) > 0,
    "batch_id must be non-empty",
)
def mark_done(kb_path: str, batch_id: str) -> dict:
    """Self-verifying close gate: runs lint_kb and closes the batch only
    when total_issues == 0. The lint count is measured, never caller-
    supplied, so the gate cannot be faked. GC is allowed only after this."""
    manifest = _load_manifest(kb_path, batch_id)
    if manifest.get("phase") not in ("merging", "linting"):
        raise ContractViolationError(
            f"batch {batch_id!r} is in phase {manifest.get('phase')!r}; "
            "run merge first, then fix lint findings, then mark-done.",
            kind="precondition",
        )
    try:
        report = lint_kb(kb_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ContractViolationError(
            f"lint failed on this KB: {exc}. Fix the underlying files, "
            "then re-run mark-done.",
            kind="io",
        )
    total = report.get("total_issues", 0)
    if total != 0:
        first = "; ".join(
            f"{i.get('type')}:{i.get('file')}"
            for i in report.get("issues", [])[:5]
        )
        raise ContractViolationError(
            f"KB has {total} outstanding lint issues ({first}). Fix every "
            "issue (usually reciprocal backlinks from the merge), re-run "
            "lint.py to confirm total_issues == 0, then mark-done.",
            kind="precondition",
        )
    report_path = _batch_dir(kb_path, batch_id) / "lint-report.json"
    _atomic_write_text(
        report_path,
        json.dumps(
            {
                "batch_id": batch_id,
                "total_issues": 0,
                "marked_at": _utc_now(),
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    manifest["phase"] = "done"
    _save_manifest(kb_path, batch_id, manifest)
    return {"batch_id": batch_id, "phase": "done"}


@precondition(
    lambda kb_path, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
@precondition(
    lambda batch_id, **_: len(batch_id.strip()) > 0,
    "batch_id must be non-empty",
)
def gc_batch(kb_path: str, batch_id: str, keep: bool = False) -> dict:
    """Delete the bulky staging scratch after a done batch. Retains the
    audit trail (manifest.json, merge-queue.json, lint-report.json,
    verify-report.json, rules-combined.md).

    Every removal is confined to the batch directory and refuses symlinks —
    knowledge/, sources/, index.md and log.md are never touched. Idempotent.
    """
    manifest = _load_manifest(kb_path, batch_id)
    if manifest.get("phase") != "done":
        raise ContractViolationError(
            f"batch {batch_id!r} is in phase {manifest.get('phase')!r}; GC "
            "needs phase 'done' (merge → lint clean → mark-done first).",
            kind="precondition",
        )
    batch_root = _batch_dir(kb_path, batch_id)
    report_path = batch_root / "lint-report.json"
    if not report_path.exists():
        raise ContractViolationError(
            f"missing lint gate record {report_path}. Re-run mark-done "
            "before GC.",
            kind="precondition",
        )
    staging = batch_root / "staging"
    removed: list[str] = []
    archived: str | None = None
    if staging.exists() or staging.is_symlink():
        if staging.is_symlink():
            raise ContractViolationError(
                f"refusing to GC symlinked staging dir: {staging}. Remove "
                "the symlink manually after inspection.",
                kind="invariant",
            )
        try:
            resolved = staging.resolve()
            root = batch_root.resolve()
        except OSError as exc:
            raise ContractViolationError(
                f"cannot resolve staging dir {staging}: {exc}.",
                kind="io",
            )
        if resolved != root and root not in resolved.parents:
            raise ContractViolationError(
                f"refusing to GC staging outside the batch dir: {staging}.",
                kind="invariant",
            )
        try:
            if keep:
                # Archive instead of deleting — debug data moves out of the
                # batch dir so a later audit can inspect worker proposals.
                # Pre-scan refuses symlinks: copytree would otherwise follow
                # planted links and pull outside content into the archive.
                for found in staging.rglob("*"):
                    if found.is_symlink():
                        raise ContractViolationError(
                            f"refusing to archive symlinked path: {found}. "
                            "Remove it manually after inspection.",
                            kind="invariant",
                        )
                archive_root = (
                    Path(kb_path) / ".kb" / "batches-archived" / batch_id
                )
                archive_root.mkdir(parents=True, exist_ok=True)
                shutil.copytree(staging, archive_root / "staging", dirs_exist_ok=True)
                archived = str(archive_root)
            shutil.rmtree(staging)
        except OSError as exc:
            raise ContractViolationError(
                f"cannot remove scratch path {staging}: {exc}.",
                kind="io",
            )
        removed.append("staging")
    return {"batch_id": batch_id, "removed": removed, "archived": archived}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Batch import reconciler.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_merge = sub.add_parser("merge")
    p_merge.add_argument("--kb-path", required=True)
    p_merge.add_argument("--batch-id", required=True)
    p_merge.add_argument("--dry-run", action="store_true")
    p_merge.add_argument("--output", "-o", type=Path, default=None)

    p_done = sub.add_parser("mark-done")
    p_done.add_argument("--kb-path", required=True)
    p_done.add_argument("--batch-id", required=True)
    p_done.add_argument("--output", "-o", type=Path, default=None)

    p_gc = sub.add_parser("gc")
    p_gc.add_argument("--kb-path", required=True)
    p_gc.add_argument("--batch-id", required=True)
    p_gc.add_argument(
        "--keep",
        action="store_true",
        help="Archive scratch under .kb/batches-archived/ instead of deleting",
    )
    p_gc.add_argument("--output", "-o", type=Path, default=None)

    args = parser.parse_args(argv)
    try:
        if args.command == "merge":
            result = merge_batch(args.kb_path, args.batch_id, dry_run=args.dry_run)
        elif args.command == "mark-done":
            result = mark_done(args.kb_path, args.batch_id)
        else:
            result = gc_batch(args.kb_path, args.batch_id, keep=args.keep)
    except ContractViolationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    emit_json_result(
        result,
        output_path=args.output,
        artifact_kind=_ARTIFACT_KINDS[args.command],
    )


if __name__ == "__main__":
    main()
