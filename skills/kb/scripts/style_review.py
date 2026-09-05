#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Manage style review records for KB style-phrase findings.

Review records are JSON files under `.kb/style-reviewed/`, named by SHA-1 of a
canonical key: `{file, line, pattern, match}`.
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

REVIEW_SCHEMA = "kb-style-review/v1"
ALLOWED_REASONS = ("subject-matter", "verbatim-quote", "other")
_REQUIRED_RECORD_FIELDS = ("key", "reason", "created")


def _review_dir(kb_path: str | Path) -> Path:
    return Path(kb_path) / ".kb" / "style-reviewed"


def _is_kb_directory(kb_path: str | Path) -> bool:
    """A KB path may not exist yet (add_review creates it), but must not be a file."""
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
    finding unreviewed forever with no error to explain it.
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
        raise ContractViolationError(f"Style review record{source} must be an object")
    for field in _REQUIRED_RECORD_FIELDS:
        if field not in record:
            raise ContractViolationError(
                f"Style review record{source} is missing required field: {field}"
            )
    if record.get("schema") != REVIEW_SCHEMA:
        raise ContractViolationError(
            f"Style review record{source} schema must be {REVIEW_SCHEMA}"
        )

    key = record["key"]
    if not isinstance(key, dict):
        raise ContractViolationError(f"Style review record{source} key must be an object")
    for field in ("file", "line", "pattern", "match"):
        if field not in key:
            raise ContractViolationError(
                f"Style review record{source} key is missing field: {field}"
            )
    if not isinstance(key["file"], str) or not key["file"].strip():
        raise ContractViolationError(f"Style review record{source} key.file must be non-empty")
    # Anything but the canonical form lint emits ("knowledge/topics/x.md") would
    # never match a finding, so reject it here instead of failing silently later.
    if (
        key["file"].startswith("/")
        or "\\" in key["file"]
        or ".." in PurePosixPath(key["file"]).parts
        or PurePosixPath(key["file"]).as_posix() != key["file"]
    ):
        raise ContractViolationError(
            f"Style review record{source} key.file must be a KB-relative posix path "
            f"in canonical form (e.g. 'knowledge/topics/x.md'): {key['file']}"
        )
    if isinstance(key["line"], bool) or not isinstance(key["line"], int) or key["line"] <= 0:
        raise ContractViolationError(f"Style review record{source} key.line must be a positive integer")
    if not isinstance(key["pattern"], str) or not key["pattern"].strip():
        raise ContractViolationError(f"Style review record{source} key.pattern must be non-empty")
    if not isinstance(key["match"], str) or not key["match"].strip():
        raise ContractViolationError(f"Style review record{source} key.match must be non-empty")

    if record["reason"] not in ALLOWED_REASONS:
        raise ContractViolationError(
            f"Style review record{source} reason must be one of: {', '.join(ALLOWED_REASONS)}"
        )
    if not isinstance(record["created"], str) or not record["created"].strip():
        raise ContractViolationError(f"Style review record{source} created must be non-empty")
    if "note" in record and not isinstance(record["note"], str):
        raise ContractViolationError(f"Style review record{source} note must be a string")

    return record


def _read_record(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractViolationError(f"Invalid style review record {path}: {exc}") from exc
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
def add_review(
    kb_path: str | Path,
    file: str,
    line: int,
    pattern: str,
    match: str,
    *,
    reason: str,
    note: str | None = None,
) -> dict:
    """Atomically create or replace one style review record."""
    key = _canonical_key(_relative_file(kb_path, file), line, pattern, match)
    record: dict = {
        "schema": REVIEW_SCHEMA,
        "key": key,
        "reason": reason,
        "created": datetime.now(timezone.utc).isoformat(),
    }
    if note is not None:
        record["note"] = note

    directory = _review_dir(kb_path)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ContractViolationError(
            f"Could not create the review directory {directory}: {exc}"
        ) from exc
    target = directory / _key_filename(key)

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
            f"Could not write the style review record {target}: {exc}"
        ) from exc
    except Exception:
        _unlink_quietly(tmp_name)
        raise

    return record


@precondition(
    lambda kb_path, **_: isinstance(kb_path, (str, Path)) and str(kb_path).strip() != "",
    "kb_path must be non-empty",
)
@precondition(
    lambda kb_path, **_: _is_kb_directory(kb_path),
    "kb_path must be a directory",
)
def list_reviews(kb_path: str | Path) -> list[dict]:
    """Return all valid review records sorted by canonical key order."""
    directory = _review_dir(kb_path)
    if not directory.exists():
        return []

    records = [_read_record(path) for path in sorted(directory.glob("*.json"))]
    return sorted(
        records,
        key=lambda record: (
            record["key"]["file"],
            record["key"]["line"],
            record["key"]["pattern"],
            record["key"]["match"],
        ),
    )


@precondition(
    lambda kb_path, **_: isinstance(kb_path, (str, Path)) and str(kb_path).strip() != "",
    "kb_path must be non-empty",
)
@precondition(
    lambda kb_path, **_: _is_kb_directory(kb_path),
    "kb_path must be a directory",
)
def load_review_records(kb_path: str | Path) -> dict:
    """Return review records keyed by `(file, line, pattern, match)`."""
    out: dict = {}
    for record in list_reviews(kb_path):
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
def remove_review(
    kb_path: str | Path,
    file: str,
    line: int,
    pattern: str,
    match: str,
) -> bool:
    """Remove one review record. Return True when a file was actually removed."""
    key = _canonical_key(_relative_file(kb_path, file), line, pattern, match)
    target = _review_dir(kb_path) / _key_filename(key)
    if not target.exists():
        return False
    try:
        target.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ContractViolationError(f"Could not remove style review record {target}: {exc}") from exc
    return True


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Manage KB style review records.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add or replace a review record")
    add_parser.add_argument("--kb", required=True, help="Path to KB directory")
    add_parser.add_argument("--file", required=True, help="KB-relative markdown path")
    add_parser.add_argument("--line", required=True, type=int, help="1-based line number")
    add_parser.add_argument("--pattern", required=True, help="Pattern id")
    add_parser.add_argument("--match", required=True, help="Exact matched text")
    add_parser.add_argument(
        "--reason",
        required=True,
        choices=ALLOWED_REASONS,
        help="Reason for suppressing the finding",
    )
    add_parser.add_argument("--note", help="Optional LLM-authored note")

    list_parser = subparsers.add_parser("list", help="List all review records")
    list_parser.add_argument("--kb", required=True, help="Path to KB directory")

    remove_parser = subparsers.add_parser("remove", help="Remove one review record")
    remove_parser.add_argument("--kb", required=True, help="Path to KB directory")
    remove_parser.add_argument("--file", required=True, help="KB-relative markdown path")
    remove_parser.add_argument("--line", required=True, type=int, help="1-based line number")
    remove_parser.add_argument("--pattern", required=True, help="Pattern id")
    remove_parser.add_argument("--match", required=True, help="Exact matched text")

    args = parser.parse_args(argv)

    try:
        if args.command == "add":
            result = add_review(
                args.kb,
                args.file,
                args.line,
                args.pattern,
                args.match,
                reason=args.reason,
                note=args.note,
            )
        elif args.command == "list":
            result = list_reviews(args.kb)
        else:
            result = {"removed": remove_review(args.kb, args.file, args.line, args.pattern, args.match)}
    except ContractViolationError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()