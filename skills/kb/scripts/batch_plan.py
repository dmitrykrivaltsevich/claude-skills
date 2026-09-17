#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml >= 6.0",
# ]
# ///
"""Batch import planner — Phase 0 of parallel kb ingestion.

Collects a directory of files (or a list file of paths/URLs), mints every
source-id centrally, pre-registers all sources sequentially via
add_source.register_source, snapshots base file hashes, and writes the batch
manifest that workers and the reconciler share.

Local imports: add_source (pyyaml), state (no third-party), contracts and
artifact_output (stdlib only) — so pyyaml is the only runtime dependency.

Unit of work: one source. Checkpoint artifact:
.kb/batches/<batch-id>/manifest.json. Resume path: re-run plan (idempotent,
returns resumed:true) or read manifest {phase, cursor}. Handoff: {batch_id}.

Output: JSON to stdout (or --output artifact envelope). Errors to stderr.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from add_source import register_source
from artifact_output import emit_json_result
from contracts import ContractViolationError, precondition
from state import add_items, init_task

# Default fan-out bound — matches the user requirement (≤10 parallel agents).
# Caps token burn and merge-queue pressure while keeping throughput high.
_MAX_WORKERS_DEFAULT = 10

# Max slug characters for a minted source-id — keeps ids readable inside
# filenames, frontmatter and wikilinks, and stays far below OS path limits.
_MAX_SLUG_CHARS = 60

# Subdirectory of .kb/ holding all batch state (manifest, staging, queue).
_BATCHES_DIRNAME = "batches"

# Top-level directories a directory scan never descends into — re-ingesting
# the KB's own bookkeeping or already-registered raw sources would duplicate
# config entries and stage the operation's own scratch files as inputs.
_SCAN_EXCLUDED_TOPS = frozenset(
    {".kb", "sources", ".git", "node_modules", "__pycache__", ".venv"}
)

# Max bytes for a worker rules proposal file — proposals are bullets with
# evidence quotes; anything larger is a misplaced extraction dump.
_MAX_PROPOSAL_BYTES = 20_480  # 20 KiB: hundreds of bullets fit, dumps do not.

# Max queue entries surfaced in batch status — status stays compact while
# naming the conflicted files; the full queue lives in merge-queue.json.
_QUEUE_STATUS_CAP = 50  # one screen of conflicts; more means refine-first.

# Top-level entries a worker may stage, mirroring knowledge/ subtrees.
# index.md / log.md / .kb/* are coordinator-owned and therefore forbidden.
_ALLOWED_STAGING_TOPS = frozenset(
    {
        "entities",
        "topics",
        "ideas",
        "locations",
        "timeline",
        "sources",
        "citations",
        "controversies",
        "meta",
        "questions",
        "assets",
    }
)

# Source-id shape shared with add_source.py (kebab-case, has a hyphen).
_SOURCE_ID_RE = re.compile(r"^[a-z][a-z0-9]+(?:-[a-z0-9]+)+$")

# Compact stdout envelopes for --output runs, keyed by subcommand — required
# by the artifact_output.emit_json_result contract (kind names the payload).
_ARTIFACT_KINDS = {
    "plan": "kb-batch-plan",
    "stage-write": "kb-batch-stage-write",
    "status": "kb-batch-status",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _batch_dir(kb_path: str, batch_id: str) -> Path:
    return Path(kb_path) / ".kb" / _BATCHES_DIRNAME / batch_id


def _manifest_path(kb_path: str, batch_id: str) -> Path:
    return _batch_dir(kb_path, batch_id) / "manifest.json"


def _atomic_write_text(path: Path, text: str) -> None:
    """Write text atomically so interrupted runs never leave half a file.

    Uses a unique temp sibling (pid + random) so concurrent writers never
    share a .tmp name; fsync before replace so a crash cannot lose bytes.
    Single-writer per batch is still assumed — this only removes tmp
    collisions, it is not a lock.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=path.name + ".",
            delete=False,
        ) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
            tmp_name = handle.name
        os.replace(tmp_name, path)
    except OSError as exc:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
        raise ContractViolationError(
            f"cannot write {path}: {exc}. Check disk space and permissions.",
            kind="io",
        )


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Byte variant of _atomic_write_text (unique tmp + fsync + replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=str(path.parent), prefix=path.name + ".", delete=False
        ) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            tmp_name = handle.name
        os.replace(tmp_name, path)
    except OSError as exc:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
        raise ContractViolationError(
            f"cannot write {path}: {exc}. Check disk space and permissions.",
            kind="io",
        )


def _confine(batch_root: Path, path: Path, what: str) -> Path:
    """Resolve path and refuse symlink escapes outside the batch dir.

    Workers stage via stage_write, but rules-proposals.md arrives via direct
    FS write, so any batch-owned write target must prove it stays inside.
    """
    try:
        resolved = path.resolve()
        root = batch_root.resolve()
    except OSError as exc:
        raise ContractViolationError(
            f"cannot resolve {what} {path}: {exc}.",
            kind="io",
        )
    if resolved != root and root not in resolved.parents:
        raise ContractViolationError(
            f"refusing to write {what} outside the batch dir: {path}.",
            kind="invariant",
        )
    # Refuse symlink-planted directories along the way: resolve() alone
    # would silently follow them, so inspect every ancestor explicitly.
    probe = path.parent
    while True:
        if probe.is_symlink():
            raise ContractViolationError(
                f"refusing to write through symlinked dir: {probe}. Remove "
                "the symlink and restage.",
                kind="invariant",
            )
        if probe == root or probe == probe.parent:
            break
        if root not in probe.resolve().parents and probe.resolve() != root:
            break
        probe = probe.parent
    return resolved


def _load_manifest(kb_path: str, batch_id: str) -> dict:
    path = _manifest_path(kb_path, batch_id)
    if not path.exists():
        raise ContractViolationError(
            f"no batch {batch_id!r} in this KB (missing {path}). "
            "Run batch_plan.py plan first.",
            kind="precondition",
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractViolationError(
            f"cannot read batch manifest {path}: {exc}. "
            "Re-run batch_plan.py plan to regenerate it.",
            kind="io",
        )


def _save_manifest(kb_path: str, batch_id: str, manifest: dict) -> None:
    manifest["updated_at"] = _utc_now()
    _atomic_write_text(
        _manifest_path(kb_path, batch_id),
        json.dumps(manifest, ensure_ascii=False, indent=2),
    )


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        slug = "src"
    if not slug[0].isalpha():
        # Source-ids must start with a letter (add_source.py contract).
        slug = "src-" + slug
    if "-" not in slug:
        # Source-ids must contain a hyphen (add_source.py contract).
        slug = slug + "-src"
    if len(slug) > _MAX_SLUG_CHARS:
        slug = slug[:_MAX_SLUG_CHARS].rstrip("-")
    return slug


def _mint_unique(base: str, taken: set[str]) -> str:
    """Append a letter suffix (real-2020 → real-2020a) until unique."""
    candidate = base
    ordinal = ord("a")
    counter = 2
    while candidate in taken or not _SOURCE_ID_RE.match(candidate):
        if ordinal <= ord("z"):
            candidate = f"{base}{chr(ordinal)}"
            ordinal += 1
        else:  # more than 26 collisions — fall back to a numeric suffix.
            candidate = f"{base}-{counter}"
            counter += 1
    return candidate


def _slug_for_url(url: str) -> str:
    parts = urlsplit(url)
    text = (parts.netloc + " " + parts.path).strip()
    return _slugify(text or url)


def _collect_inputs(input_spec: str) -> list[dict]:
    """Collect batch inputs preserving caller order (list file) or sorted
    byte order (directory scan, deterministic across runs)."""
    spec = Path(input_spec)
    if input_spec.startswith("http://") or input_spec.startswith("https://"):
        raise ContractViolationError(
            f"got a bare URL as --input: {input_spec}. Write the URLs, one "
            "per line, to a .txt list file (e.g. /tmp/<batch-id>-inputs.txt) "
            "and pass that path as --input instead.",
            kind="precondition",
        )
    if not spec.exists():
        raise ContractViolationError(
            f"input not found: {input_spec}. Provide a directory of source "
            "files or a .txt list file with one path/URL per line.",
            kind="precondition",
        )
    entries: list[dict] = []
    if spec.is_dir():
        found = sorted(
            (p for p in spec.rglob("*") if p.is_file()),
            key=lambda p: p.relative_to(spec).as_posix(),
        )
        for found_path in found:
            rel_parts = found_path.relative_to(spec).parts
            if any(part.startswith(".") for part in rel_parts):
                continue  # skip hidden files such as .DS_Store.
            if rel_parts[0] in _SCAN_EXCLUDED_TOPS:
                continue  # never re-ingest KB bookkeeping or raw sources.
            # Resolved absolute locations keep the manifest fingerprint
            # stable across relative-vs-absolute spellings of one input set.
            entries.append(
                {
                    "kind": "file",
                    "location": str(found_path.resolve()),
                    "input_name": found_path.name,
                    "title": found_path.stem,
                }
            )
    else:
        try:
            lines = spec.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            raise ContractViolationError(
                f"cannot read input list {spec}: {exc}. Save it as utf-8 "
                "text, one path/URL per line.",
                kind="io",
            )
        for lineno, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("http://") or line.startswith("https://"):
                entries.append(
                    {
                        "kind": "reference",
                        "location": line,
                        "input_name": line.rsplit("/", 1)[-1] or line,
                        "title": line,
                    }
                )
            else:
                candidate = Path(line)
                if not candidate.is_absolute():
                    # Relative entries resolve against the list file's
                    # directory so batches are relocatable and deterministic.
                    candidate = spec.parent / line
                if not candidate.exists():
                    raise ContractViolationError(
                        f"input list line {lineno}: file not found: {line} "
                        f"(resolved to {candidate}). Fix the path or drop "
                        "the line.",
                        kind="precondition",
                    )
                entries.append(
                    {
                        "kind": "file",
                        "location": str(candidate.resolve()),
                        "input_name": candidate.name,
                        "title": candidate.stem,
                    }
                )
    seen: set[str] = set()
    unique: list[dict] = []
    for entry in entries:
        if entry["location"] not in seen:
            seen.add(entry["location"])
            unique.append(entry)
    if not unique:
        raise ContractViolationError(
            f"no usable inputs in {input_spec}. Provide at least one source "
            "file or URL.",
            kind="precondition",
        )
    return unique


def _snapshot_base(kb_path: str) -> tuple[dict[str, str], list[str]]:
    """Record sha1 of every live knowledge file + index/log for MVCC-style
    fast-forward detection during merge. Unreadable files are reported, never
    fatal and never silent — the caller stores them on the manifest."""
    root = Path(kb_path)
    base: dict[str, str] = {}
    unreadable: list[str] = []
    knowledge = root / "knowledge"
    if knowledge.exists():
        snapshot_targets = list(knowledge.rglob("*.md"))
        # Asset blobs are versioned too — binary changes must be visible to
        # external-change detection, not just markdown edits.
        assets = knowledge / "assets"
        if assets.exists():
            snapshot_targets.extend(
                p for p in assets.rglob("*") if p.is_file() and not p.is_symlink()
            )
        for found in snapshot_targets:
            rel = found.relative_to(root).as_posix()
            try:
                base[rel] = _sha1_bytes(found.read_bytes())
            except OSError:
                # Recorded on the manifest — merge surfaces it explicitly.
                unreadable.append(rel)
    for top in ("index.md", "log.md"):
        candidate = root / top
        if candidate.exists():
            try:
                base[top] = _sha1_bytes(candidate.read_bytes())
            except OSError:
                unreadable.append(top)
    return base, unreadable


def _is_allowed_rel(rel_path: str) -> bool:
    """Staged paths must mirror a knowledge/ subtree; coordinator-owned
    files (index.md, log.md, .kb/*) are rejected here, not at merge time."""
    parts = Path(rel_path).parts
    if not parts:
        return False
    if parts[0] not in _ALLOWED_STAGING_TOPS:
        return False
    if rel_path.endswith("/"):
        return False
    name = parts[-1]
    if not name or name.startswith("."):
        return False
    if len(parts) == 1 and not name.endswith(".md"):
        return False
    if "timeline" in parts[:2] and not name.endswith(".md"):
        return False
    # Outside assets/, only markdown entries are mergeable — an extensionless
    # path would fall into the binary-variant branch at merge time.
    if parts[0] != "assets" and not name.endswith(".md"):
        return False
    return True


def _assets_owner_ok(rel_path: str, source_id: str) -> bool:
    """Assets are namespaced per source (assets/<source-id>/...) so workers
    cannot overwrite each other's blobs — enforced at stage time."""
    parts = Path(rel_path).parts
    if parts[0] != "assets":
        return True
    return len(parts) >= 3 and parts[1] == source_id


def _partition_waves(order: list[str], max_workers: int) -> list[list[str]]:
    """Split manifest order into dispatch waves of at most max_workers.

    Waves preserve global order (concatenated waves == order) and are
    disjoint/complete, so the coordinator can dispatch one wave of parallel
    workers at a time for arbitrarily large batches without any claim
    protocol — each worker owns its listed sources exclusively.
    """
    return [order[i : i + max_workers] for i in range(0, len(order), max_workers)]


def _config_sources(kb_path: str) -> list[dict]:
    """Load the config registry with malformed-entry validation (a bare
    KeyError here would hide which entry broke)."""
    config_path = Path(kb_path) / ".kb" / "config.yaml"
    if not config_path.exists():
        raise ContractViolationError(
            f"KB config not found: {config_path}. Run init.py first.",
            kind="precondition",
        )
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ContractViolationError(
            f"cannot read KB config {config_path}: {exc}.",
            kind="io",
        )
    sources = config.get("sources") or []
    for pos, entry in enumerate(sources):
        if not isinstance(entry, dict) or not entry.get("id"):
            raise ContractViolationError(
                f"KB config entry #{pos} is malformed (missing id). Fix "
                f"{config_path} before planning a batch.",
                kind="invariant",
            )
    return sources


def _ensure_registered(
    kb_path: str, entry: dict, source_id: str, taken: set[str]
) -> str:
    """Register entry under source_id, reusing an existing registration for
    the same location. Location-reuse makes crash-retries safe: a rerun
    adopts the partial run's ids instead of minting suffixed duplicates."""
    for known in _config_sources(kb_path):
        if known.get("location") == entry["location"]:
            taken.add(known["id"])
            if known["id"] != source_id:
                raise ContractViolationError(
                    f"location {entry['location']} is already registered as "
                    f"{known['id']!r}, conflicting with batch id "
                    f"{source_id!r}. To retry this batch, re-run plan with "
                    "the same batch-id; a fresh batch-id requires disjoint "
                    "inputs.",
                    kind="precondition",
                )
            return known["id"]
    if entry["kind"] == "reference":
        register_source(
            kb_path,
            entry["location"],
            source_id=source_id,
            is_reference=True,
            title=entry["title"],
        )
    else:
        register_source(
            kb_path,
            entry["location"],
            source_id=source_id,
            title=entry["title"],
        )
    taken.add(source_id)
    return source_id


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@precondition(
    lambda kb_path, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
@precondition(
    lambda input_spec, **_: len(input_spec.strip()) > 0,
    "input must be non-empty",
)
@precondition(
    lambda batch_id, **_: len(batch_id.strip()) > 0,
    "batch_id must be non-empty",
)
@precondition(
    lambda batch_id, **_: bool(re.match(r"^[a-z0-9][a-z0-9-]*$", batch_id)),
    "batch_id must be kebab-case (e.g. batch-001)",
)
@precondition(
    lambda max_workers, **_: 1 <= max_workers <= _MAX_WORKERS_DEFAULT,
    f"max_workers must be between 1 and {_MAX_WORKERS_DEFAULT}",
)
def plan_batch(
    kb_path: str,
    input_spec: str,
    batch_id: str,
    max_workers: int = _MAX_WORKERS_DEFAULT,
    state_dir: Path | str | None = None,
) -> dict:
    """Mint ids, pre-register every source, snapshot base, write manifest.

    Idempotent: re-running with the same batch_id and identical inputs
    returns resumed:true and registers nothing twice. Re-running with
    *different* inputs raises (a batch-id names one fixed input set).
    Crash-safe: the manifest is pre-written with phase "planning" before
    registration, and registration reuses locations, so a retry adopts the
    partial run's ids instead of minting suffixed duplicates.
    """
    entries = _collect_inputs(input_spec)
    fingerprint = hashlib.sha1(
        json.dumps(
            [(e["kind"], e["location"]) for e in entries],
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    manifest_file = _manifest_path(kb_path, batch_id)
    if manifest_file.exists():
        manifest = _load_manifest(kb_path, batch_id)
        if manifest.get("fingerprint") != fingerprint:
            raise ContractViolationError(
                f"batch_id {batch_id!r} already plans different inputs. Use "
                "a fresh batch-id for a new input set.",
                kind="precondition",
            )
        if manifest.get("phase") != "planning":
            if "waves" not in manifest:
                raise ContractViolationError(
                    f"batch manifest {manifest_file} is malformed (missing "
                    "waves). Delete the batch dir and re-run plan with a "
                    "fresh batch-id.",
                    kind="invariant",
                )
            waves = manifest["waves"]
            return {
                "batch_id": batch_id,
                "manifest_path": str(manifest_file),
                "source_ids": manifest["order"],
                "total_sources": len(manifest["order"]),
                "waves": waves,
                "resumed": True,
            }
        # Crash during registration — fall through and finish it below,
        # reusing the pre-written order and existing registrations.
        sources = manifest["sources"]
        order = manifest["order"]
    else:
        taken = {s["id"] for s in _config_sources(kb_path)}
        sources = []
        for entry in entries:
            if entry["kind"] == "reference":
                base = _slug_for_url(entry["location"])
            else:
                base = _slugify(Path(entry["input_name"]).stem)
            source_id = _mint_unique(base, taken)
            taken.add(source_id)
            sources.append(
                {
                    "source_id": source_id,
                    "kind": entry["kind"],
                    "location": entry["location"],
                    "input_name": entry["input_name"],
                    "title": entry["title"],
                }
            )
        order = [s["source_id"] for s in sources]
        _save_manifest(
            kb_path,
            batch_id,
            {
                "batch_id": batch_id,
                "kb_path": str(Path(kb_path)),
                "order": order,
                "sources": sources,
                "fingerprint": fingerprint,
                "base": {},
                "snapshot_unreadable": [],
                "phase": "planning",
                "cursor": {"applied_total": 0},
                "max_workers": max_workers,
                "waves": _partition_waves(order, max_workers),
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
            },
        )

    taken = {s["id"] for s in _config_sources(kb_path)}
    for source in sources:
        entry = {
            "kind": source["kind"],
            "location": source["location"],
            "title": source["title"],
        }
        _ensure_registered(kb_path, entry, source["source_id"], taken)
    resolved_state_dir = (
        Path(state_dir) if state_dir else Path(kb_path) / ".kb" / "tasks"
    )
    task_id = f"batch-{batch_id}"
    init_task(
        task_id,
        "add",
        f"Batch import {batch_id}: {len(order)} sources",
        kb_path,
        state_dir=resolved_state_dir,
    )
    add_items(
        task_id,
        [
            {"title": f"ingest {s['source_id']}: {s['input_name']}"}
            for s in sources
        ],
        state_dir=resolved_state_dir,
    )

    base, unreadable = _snapshot_base(kb_path)
    waves = _partition_waves(order, max_workers)
    manifest = {
        "batch_id": batch_id,
        "kb_path": str(Path(kb_path)),
        "order": order,
        "sources": sources,
        "fingerprint": fingerprint,
        "base": base,
        "snapshot_unreadable": unreadable,
        "phase": "mapping",
        "cursor": {"applied_total": 0},
        "max_workers": max_workers,
        "waves": waves,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
    }
    _save_manifest(kb_path, batch_id, manifest)
    return {
        "batch_id": batch_id,
        "manifest_path": str(manifest_file),
        "source_ids": order,
        "total_sources": len(order),
        "waves": waves,
        "resumed": False,
    }


@precondition(
    lambda kb_path, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
@precondition(
    lambda batch_id, **_: len(batch_id.strip()) > 0,
    "batch_id must be non-empty",
)
@precondition(
    lambda source_id, **_: bool(_SOURCE_ID_RE.match(source_id)),
    "source_id must be kebab-case (e.g. real-2020)",
)
@precondition(
    lambda rel_path, **_: len(rel_path.strip()) > 0
    and ".." not in Path(rel_path).parts
    and not Path(rel_path).is_absolute()
    and _is_allowed_rel(rel_path),
    "rel_path must mirror a knowledge/ subtree (e.g. entities/ada.md); "
    "index.md, log.md and .kb/* are forbidden — the reconciler owns them",
)
@precondition(
    lambda rel_path, source_id, **_: _assets_owner_ok(rel_path, source_id),
    "assets must be namespaced per source (assets/<source-id>/...) so "
    "workers cannot overwrite each other's blobs",
)
@precondition(
    lambda content_file, **_: len(content_file.strip()) > 0,
    "content_file must be non-empty",
)
def stage_write(
    kb_path: str,
    batch_id: str,
    source_id: str,
    rel_path: str,
    content_file: str,
) -> dict:
    """Stage one worker proposal: atomic copy + ops.jsonl entry.

    Each source owns exactly one ops.jsonl, so concurrent workers never
    share a file. Returns base/staged hashes for merge-time MVCC checks.
    """
    manifest = _load_manifest(kb_path, batch_id)
    if source_id not in manifest["order"]:
        raise ContractViolationError(
            f"source {source_id!r} is not part of batch {batch_id!r} "
            f"(order: {manifest['order']}). Check the source-id spelling.",
            kind="precondition",
        )
    content_path = Path(content_file)
    if not content_path.exists():
        raise ContractViolationError(
            f"content file not found: {content_file}. Write the proposal "
            "body to a temp file first, then stage it.",
            kind="precondition",
        )
    try:
        data = content_path.read_bytes()
    except OSError as exc:
        raise ContractViolationError(
            f"cannot read content file {content_file}: {exc}.",
            kind="io",
        )

    live_path = Path(kb_path) / "knowledge" / rel_path
    try:
        base_sha1 = _sha1_bytes(live_path.read_bytes()) if live_path.exists() else ""
    except OSError as exc:
        raise ContractViolationError(
            f"cannot hash live file {live_path}: {exc}.",
            kind="io",
        )
    staged_sha1 = _sha1_bytes(data)
    batch_root = _batch_dir(kb_path, batch_id)
    staged_path = batch_root / "staging" / source_id / rel_path
    _confine(batch_root, staged_path, "staged proposal")
    _atomic_write_bytes(staged_path, data)

    ops_path = batch_root / "staging" / source_id / "ops.jsonl"
    _confine(batch_root, ops_path, "staging ops log")
    ops_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "op": "create" if not base_sha1 else "update",
        "path": rel_path,
        "base_sha1": base_sha1,
        "staged_sha1": staged_sha1,
        "source_id": source_id,
        "staged_at": _utc_now(),
    }
    try:
        with ops_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise ContractViolationError(
            f"cannot append {ops_path}: {exc}. Check disk space.",
            kind="io",
        )
    return record


@precondition(
    lambda kb_path, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
@precondition(
    lambda batch_id, **_: len(batch_id.strip()) > 0,
    "batch_id must be non-empty",
)
def batch_status(
    kb_path: str,
    batch_id: str,
    output_path: str | None = None,
) -> dict:
    """Report batch progress. Read-only: the only permitted write is the
    caller-named output_path artifact file, which must live outside the
    KB's .kb/ tree so status checks never perturb batch mtimes."""
    manifest = _load_manifest(kb_path, batch_id)
    staging_root = _batch_dir(kb_path, batch_id) / "staging"
    per_source: dict[str, dict] = {}
    for source_id in manifest["order"]:
        ops_path = staging_root / source_id / "ops.jsonl"
        entry: dict = {"ops": 0, "error": None}
        if ops_path.exists():
            try:
                with ops_path.open(encoding="utf-8") as handle:
                    for line in handle:
                        if not line.strip():
                            continue
                        parsed = json.loads(line)
                        if not isinstance(parsed, dict) or not isinstance(
                            parsed.get("path"), str
                        ):
                            raise ValueError(f"bad ops record: {line.strip()[:80]}")
                        entry["ops"] += 1
            except (OSError, ValueError) as exc:
                # Explicit error payload, never a magic number — merge will
                # refuse the corrupt log with the same detail.
                entry["error"] = f"unreadable ops log: {exc}"
        per_source[source_id] = entry
    queue_path = _batch_dir(kb_path, batch_id) / "merge-queue.json"
    escalated: dict = {"files": 0, "error": None, "entries": []}
    if queue_path.exists():
        try:
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
            entries = queue.get("entries", [])
            escalated["files"] = len(entries)
            escalated["entries"] = [
                {
                    "path": e.get("path", ""),
                    "parties": e.get("parties", []),
                    "needs_llm": e.get("needs_llm", False),
                }
                for e in entries[:_QUEUE_STATUS_CAP]
            ]
        except (OSError, json.JSONDecodeError) as exc:
            escalated["error"] = f"unreadable merge queue: {exc}"
    result = {
        "batch_id": batch_id,
        "phase": manifest.get("phase", ""),
        "total_sources": len(manifest["order"]),
        "staged_ops": per_source,
        "escalated": escalated,
        "snapshot_unreadable": manifest.get("snapshot_unreadable", []),
        "cursor": manifest.get("cursor", {}),
    }
    if output_path:
        _reject_kb_internal_output(kb_path, output_path)
        _atomic_write_text(
            Path(output_path),
            json.dumps(result, ensure_ascii=False, indent=2),
        )
    return result


def _reject_kb_internal_output(kb_path: str, output_path: str) -> None:
    """Refuse artifact outputs inside the KB's .kb/ tree — a status check
    must never perturb the state it reports on."""
    try:
        target = Path(output_path).resolve()
        internal = (Path(kb_path) / ".kb").resolve()
    except OSError as exc:
        raise ContractViolationError(
            f"cannot resolve output path {output_path}: {exc}.",
            kind="io",
        )
    if target == internal or internal in target.parents:
        raise ContractViolationError(
            f"output {output_path} must live outside the KB's .kb/ tree "
            "(e.g. /tmp/status.json) so reporting stays read-only.",
            kind="precondition",
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Batch import planner.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan")
    p_plan.add_argument("--kb-path", required=True)
    p_plan.add_argument(
        "--input",
        required=True,
        help="Directory of source files or .txt list (paths/URLs, order kept)",
    )
    p_plan.add_argument("--batch-id", required=True)
    p_plan.add_argument("--max-workers", type=int, default=_MAX_WORKERS_DEFAULT)
    p_plan.add_argument("--state-dir", type=Path, default=None)
    p_plan.add_argument("--output", "-o", type=Path, default=None)

    p_stage = sub.add_parser("stage-write")
    p_stage.add_argument("--kb-path", required=True)
    p_stage.add_argument("--batch-id", required=True)
    p_stage.add_argument("--source-id", required=True)
    p_stage.add_argument(
        "--path", required=True, help="knowledge-relative path to stage"
    )
    p_stage.add_argument("--content-file", required=True)
    p_stage.add_argument("--output", "-o", type=Path, default=None)

    p_status = sub.add_parser("status")
    p_status.add_argument("--kb-path", required=True)
    p_status.add_argument("--batch-id", required=True)
    p_status.add_argument("--output", "-o", type=Path, default=None)

    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            result = plan_batch(
                args.kb_path,
                args.input,
                args.batch_id,
                max_workers=args.max_workers,
                state_dir=args.state_dir,
            )
        elif args.command == "stage-write":
            result = stage_write(
                args.kb_path,
                args.batch_id,
                args.source_id,
                args.path,
                args.content_file,
            )
        else:
            # batch_status writes the raw report itself when --output is
            # given (single write); here we only need the stdout envelope.
            # The .kb/ guard applies to CLI outputs too — a status check
            # must never perturb the state it reports on.
            if args.output:
                _reject_kb_internal_output(args.kb_path, str(args.output))
            result = batch_status(args.kb_path, args.batch_id)
            if args.output:
                emit_json_result(
                    result,
                    output_path=args.output,
                    artifact_kind=_ARTIFACT_KINDS["status"],
                )
                return
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
