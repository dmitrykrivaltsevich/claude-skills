#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Manage style exceptions for KB style-phrase findings.

An exception records a finding kb:lint **accepted** rather than fixed — a
verbatim quote, this KB's domain vocabulary, or a phrase that survived three
rewrite attempts.  Fixed findings leave no file behind: the rewritten text is
the record.  So this store is the standing accepted set, not lint scratch.

Exceptions are JSON files under `.kb/style-exceptions/`, named by SHA-1 of a
canonical key: `{file, line, pattern, match}`.

Reads merge in a pre-rename `.kb/style-reviewed/` where one still exists; only
`add` and `remove` migrate it across, so reading a KB never writes to it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

sys.path.insert(0, os.path.dirname(__file__))
from contracts import ContractViolationError, precondition

EXCEPTION_SCHEMA = "kb-style-exception/v1"
# Accepted on read so a KB written before the rename keeps its exceptions.
_LEGACY_SCHEMA = "kb-style-review/v1"
_LEGACY_DIR_NAME = "style-reviewed"
_MARKER_NAME = "README.md"
_MARKER_TEXT = """# Style exceptions — durable KB data, not temporary files

Each `<sha1>.json` here records one style-phrase finding that `kb:lint`
**accepted** instead of fixing: a verbatim quote from a source, this KB's own
domain vocabulary, or a phrase three rewrite attempts could not remove.

This is not temporary lint output. A finding that was *fixed* leaves no file —
the rewritten sentence is the record. Every file here is a standing decision,
and the phrase it covers is still in the KB on purpose. Delete this directory
and the next lint re-triages all of them, and may rewrite a source's own words.

Managed by `style_exceptions.py add/list/remove`. Do not hand-edit.
"""
ALLOWED_REASONS = ("subject-matter", "verbatim-quote", "other")
_REQUIRED_RECORD_FIELDS = ("key", "reason", "created")


def _exception_dir(kb_path: str | Path) -> Path:
    return Path(kb_path) / ".kb" / "style-exceptions"


def _legacy_dir(kb_path: str | Path) -> Path:
    return Path(kb_path) / ".kb" / _LEGACY_DIR_NAME


def _record_files(kb_path: str | Path) -> list[Path]:
    """Every record file, legacy directory first so a current record wins."""
    files: list[Path] = []
    for directory in (_legacy_dir(kb_path), _exception_dir(kb_path)):
        if directory.is_dir():
            files.extend(sorted(directory.glob("*.json")))
    return files


def _write_marker(directory: Path) -> None:
    """Explain the directory in place, so it never reads as lint scratch.

    Best-effort: a KB on read-only media should still be listable.
    """
    try:
        (directory / _MARKER_NAME).write_text(_MARKER_TEXT, encoding="utf-8")
    except OSError:
        pass


def _write_record(target: Path, record: dict) -> None:
    """Write one record atomically — an interrupted write must leave no half file."""
    directory = target.parent
    try:
        fd, tmp_name = tempfile.mkstemp(dir=directory, prefix=f".{target.name}.", suffix=".tmp")
    except OSError as exc:
        raise ContractViolationError(
            f"Could not create a temporary file in {directory}: {exc}"
        ) from exc

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp_name, target)
    except OSError as exc:
        _unlink_quietly(tmp_name)
        raise ContractViolationError(
            f"Could not write the style exception {target}: {exc}"
        ) from exc
    except Exception:
        _unlink_quietly(tmp_name)
        raise


def _upgrade_schema(path: Path) -> None:
    """Stamp a migrated record with the current schema."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        # Leave it: _read_record raises an actionable error for it later.
        return
    if not isinstance(record, dict) or record.get("schema") != _LEGACY_SCHEMA:
        return
    record["schema"] = EXCEPTION_SCHEMA
    _write_record(path, record)


def _migrate_legacy_dir(kb_path: str | Path) -> int:
    """Move a pre-rename `.kb/style-reviewed/` across. Mutating callers only.

    Reads merge the two directories instead of calling this, so linting a
    read-only KB stays read-only and concurrent runs cannot race each other.
    """
    legacy = _legacy_dir(kb_path)
    if not legacy.is_dir():
        return 0
    target = _exception_dir(kb_path)
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ContractViolationError(
            f"Could not create the exception directory {target}: {exc}"
        ) from exc

    migrated = 0
    for path in sorted(legacy.iterdir()):
        if not path.is_file():
            continue
        destination = target / path.name
        # The name is the SHA-1 of the key, so a collision is the same finding:
        # the current record already supersedes this one. Leave it rather than
        # overwrite a decision, and let reads keep merging it.
        if destination.exists():
            continue
        try:
            os.replace(path, destination)
        except OSError as exc:
            raise ContractViolationError(
                f"Could not migrate {path} to {destination}: {exc}"
            ) from exc
        _upgrade_schema(destination)
        migrated += 1

    _write_marker(target)
    try:
        legacy.rmdir()
    except OSError:
        # Superseded copies remain; reads still merge them, so nothing is lost.
        pass
    if migrated:
        print(
            f"note: migrated {migrated} style exception(s) from {legacy.name}/ to {target.name}/",
            file=sys.stderr,
        )
    return migrated


def _is_kb_directory(kb_path: str | Path) -> bool:
    """A KB path may not exist yet (add_exception creates it), but must not be a file."""
    path = Path(kb_path)
    return not path.exists() or path.is_dir()


def _unlink_quietly(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _relative_file(kb_path: str | Path, file: str) -> str:
    """Return `file` as the KB-relative posix path that lint uses in its findings.

    Accepts the shapes a caller plausibly produces — an absolute path, a `./`
    prefix, backslash separators — because a key that merely *looks* different
    from lint's `relative_to(root).as_posix()` never matches, leaving the
    finding un-excepted forever with no error to explain it.
    """
    root = Path(kb_path).resolve()
    raw = str(file).replace("\\", "/").strip()
    path = Path(raw)
    if not path.is_absolute():
        path = root / raw
    try:
        relative = path.resolve().relative_to(root)
    except ValueError as exc:
        raise ContractViolationError(
            f"file must be a path inside the KB ({root}): {file}"
        ) from exc
    if not relative.parts:
        raise ContractViolationError(
            f"file must name a markdown file inside the KB: {file}"
        )
    return relative.as_posix()


def _is_within_kb(kb_path: str | Path, file: str) -> bool:
    try:
        _relative_file(kb_path, file)
    except ContractViolationError:
        return False
    return True


def _canonical_key(file: str, line: int, pattern: str, match: str) -> dict:
    return {
        "file": file,
        "line": line,
        "pattern": pattern,
        "match": match,
    }


def _key_filename(key: dict) -> str:
    canonical = json.dumps(
        key,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha1(canonical).hexdigest() + ".json"


def _validate_record(record: object, path: Path | None = None) -> dict:
    source = f" in {path}" if path is not None else ""
    if not isinstance(record, dict):
        raise ContractViolationError(f"Style exception record{source} must be an object")
    for field in _REQUIRED_RECORD_FIELDS:
        if field not in record:
            raise ContractViolationError(
                f"Style exception record{source} is missing required field: {field}"
            )
    if record.get("schema") not in (EXCEPTION_SCHEMA, _LEGACY_SCHEMA):
        raise ContractViolationError(
            f"Style exception record{source} schema must be {EXCEPTION_SCHEMA}"
        )

    key = record["key"]
    if not isinstance(key, dict):
        raise ContractViolationError(f"Style exception record{source} key must be an object")
    for field in ("file", "line", "pattern", "match"):
        if field not in key:
            raise ContractViolationError(
                f"Style exception record{source} key is missing field: {field}"
            )
    if not isinstance(key["file"], str) or not key["file"].strip():
        raise ContractViolationError(f"Style exception record{source} key.file must be non-empty")
    # Anything but the canonical form lint emits ("knowledge/topics/x.md") would
    # never match a finding, so reject it here instead of failing silently later.
    if (
        key["file"].startswith("/")
        or "\\" in key["file"]
        or ".." in PurePosixPath(key["file"]).parts
        or PurePosixPath(key["file"]).as_posix() != key["file"]
    ):
        raise ContractViolationError(
            f"Style exception record{source} key.file must be a KB-relative posix path "
            f"in canonical form (e.g. 'knowledge/topics/x.md'): {key['file']}"
        )
    if isinstance(key["line"], bool) or not isinstance(key["line"], int) or key["line"] <= 0:
        raise ContractViolationError(f"Style exception record{source} key.line must be a positive integer")
    if not isinstance(key["pattern"], str) or not key["pattern"].strip():
        raise ContractViolationError(f"Style exception record{source} key.pattern must be non-empty")
    if not isinstance(key["match"], str) or not key["match"].strip():
        raise ContractViolationError(f"Style exception record{source} key.match must be non-empty")

    if record["reason"] not in ALLOWED_REASONS:
        raise ContractViolationError(
            f"Style exception record{source} reason must be one of: {', '.join(ALLOWED_REASONS)}"
        )
    if not isinstance(record["created"], str) or not record["created"].strip():
        raise ContractViolationError(f"Style exception record{source} created must be non-empty")
    if "note" in record and not isinstance(record["note"], str):
        raise ContractViolationError(f"Style exception record{source} note must be a string")

    return record


def _read_record(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractViolationError(f"Invalid style exception record {path}: {exc}") from exc
    return _validate_record(data, path)


@precondition(
    lambda kb_path, **_: isinstance(kb_path, (str, Path)) and str(kb_path).strip() != "",
    "kb_path must be non-empty",
)
@precondition(
    lambda kb_path, **_: _is_kb_directory(kb_path),
    "kb_path must be a directory",
)
@precondition(
    lambda file, **_: isinstance(file, str) and file.strip() != "",
    "file must be non-empty",
)
@precondition(
    lambda kb_path, file, **_: _is_within_kb(kb_path, file),
    "file must be a path inside the KB",
)
@precondition(
    lambda line, **_: (
        not isinstance(line, bool) and isinstance(line, int) and line > 0
    ),
    "line must be a positive integer",
)
@precondition(
    lambda pattern, **_: isinstance(pattern, str) and pattern.strip() != "",
    "pattern must be non-empty",
)
@precondition(
    lambda match, **_: isinstance(match, str) and match.strip() != "",
    "match must be non-empty",
)
@precondition(
    lambda reason, **_: reason in ALLOWED_REASONS,
    f"reason must be one of: {', '.join(ALLOWED_REASONS)}",
)
@precondition(
    lambda note, **_: note is None or isinstance(note, str),
    "note must be a string or None",
)
def add_exception(
    kb_path: str | Path,
    file: str,
    line: int,
    pattern: str,
    match: str,
    *,
    reason: str,
    note: str | None = None,
) -> dict:
    """Atomically create or replace one style exception."""
    key = _canonical_key(_relative_file(kb_path, file), line, pattern, match)
    record: dict = {
        "schema": EXCEPTION_SCHEMA,
        "key": key,
        "reason": reason,
        "created": datetime.now(timezone.utc).isoformat(),
    }
    if note is not None:
        record["note"] = note

    _migrate_legacy_dir(kb_path)
    directory = _exception_dir(kb_path)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ContractViolationError(
            f"Could not create the exception directory {directory}: {exc}"
        ) from exc
    _write_marker(directory)
    _write_record(directory / _key_filename(key), record)

    return record


@precondition(
    lambda kb_path, **_: isinstance(kb_path, (str, Path)) and str(kb_path).strip() != "",
    "kb_path must be non-empty",
)
@precondition(
    lambda kb_path, **_: _is_kb_directory(kb_path),
    "kb_path must be a directory",
)
def list_exceptions(kb_path: str | Path) -> list[dict]:
    """Return all valid exceptions sorted by canonical key order.

    Read-only: a legacy `.kb/style-reviewed/` is merged in place, not moved.
    """
    by_key: dict[tuple, dict] = {}
    for path in _record_files(kb_path):
        record = _read_record(path)
        key = record["key"]
        by_key[(key["file"], key["line"], key["pattern"], key["match"])] = record
    return [record for _, record in sorted(by_key.items())]


@precondition(
    lambda kb_path, **_: isinstance(kb_path, (str, Path)) and str(kb_path).strip() != "",
    "kb_path must be non-empty",
)
@precondition(
    lambda kb_path, **_: _is_kb_directory(kb_path),
    "kb_path must be a directory",
)
def load_exception_records(kb_path: str | Path) -> dict:
    """Return exceptions keyed by `(file, line, pattern, match)`."""
    out: dict = {}
    for record in list_exceptions(kb_path):
        key = record["key"]
        out[(key["file"], key["line"], key["pattern"], key["match"])] = record
    return out


@precondition(
    lambda kb_path, **_: isinstance(kb_path, (str, Path)) and str(kb_path).strip() != "",
    "kb_path must be non-empty",
)
@precondition(
    lambda kb_path, **_: _is_kb_directory(kb_path),
    "kb_path must be a directory",
)
@precondition(
    lambda file, **_: isinstance(file, str) and file.strip() != "",
    "file must be non-empty",
)
@precondition(
    lambda kb_path, file, **_: _is_within_kb(kb_path, file),
    "file must be a path inside the KB",
)
@precondition(
    lambda line, **_: (
        not isinstance(line, bool) and isinstance(line, int) and line > 0
    ),
    "line must be a positive integer",
)
@precondition(
    lambda pattern, **_: isinstance(pattern, str) and pattern.strip() != "",
    "pattern must be non-empty",
)
@precondition(
    lambda match, **_: isinstance(match, str) and match.strip() != "",
    "match must be non-empty",
)
def remove_exception(
    kb_path: str | Path,
    file: str,
    line: int,
    pattern: str,
    match: str,
) -> bool:
    """Remove one exception. Return True when a file was actually removed."""
    _migrate_legacy_dir(kb_path)
    key = _canonical_key(_relative_file(kb_path, file), line, pattern, match)
    name = _key_filename(key)
    removed = False
    # Both locations: a superseded legacy copy left by migration would
    # otherwise resurface on the next read as a live exception.
    for directory in (_exception_dir(kb_path), _legacy_dir(kb_path)):
        target = directory / name
        if not target.exists():
            continue
        try:
            target.unlink()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ContractViolationError(f"Could not remove style exception {target}: {exc}") from exc
        removed = True
    return removed


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Manage KB style exceptions — findings kb:lint accepted rather than fixed.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add or replace an exception")
    add_parser.add_argument("--kb", required=True, help="Path to KB directory")
    add_parser.add_argument("--file", required=True, help="KB-relative markdown path")
    add_parser.add_argument("--line", required=True, type=int, help="1-based line number")
    add_parser.add_argument("--pattern", required=True, help="Pattern id")
    add_parser.add_argument("--match", required=True, help="Exact matched text")
    add_parser.add_argument(
        "--reason",
        required=True,
        choices=ALLOWED_REASONS,
        help="Why the phrase is legitimate here",
    )
    add_parser.add_argument("--note", help="Optional LLM-authored note")

    list_parser = subparsers.add_parser("list", help="List all exceptions")
    list_parser.add_argument("--kb", required=True, help="Path to KB directory")

    remove_parser = subparsers.add_parser("remove", help="Remove one exception")
    remove_parser.add_argument("--kb", required=True, help="Path to KB directory")
    remove_parser.add_argument("--file", required=True, help="KB-relative markdown path")
    remove_parser.add_argument("--line", required=True, type=int, help="1-based line number")
    remove_parser.add_argument("--pattern", required=True, help="Pattern id")
    remove_parser.add_argument("--match", required=True, help="Exact matched text")

    args = parser.parse_args(argv)

    try:
        if args.command == "add":
            result = add_exception(
                args.kb,
                args.file,
                args.line,
                args.pattern,
                args.match,
                reason=args.reason,
                note=args.note,
            )
        elif args.command == "list":
            result = list_exceptions(args.kb)
        else:
            result = {"removed": remove_exception(args.kb, args.file, args.line, args.pattern, args.match)}
    except ContractViolationError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()