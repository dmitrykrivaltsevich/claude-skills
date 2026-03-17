#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""File inventory scanner — enumerates files with content hashes.

Walks provided paths (files or directories), computes SHA-256 hashes,
and outputs a sorted JSON array of {path, size, hash} records to stdout.
Skips commonly irrelevant directories (.git, __pycache__, node_modules, etc.)
by default.

This script is a data pipe: file system → structured JSON to stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Directories excluded by default — not worth reviewing.
_DEFAULT_EXCLUDES = frozenset({
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    ".tox",
    ".venv",
    "venv",
    ".eggs",
    "*.egg-info",
    "dist",
    "build",
})


def _hash_file(path: Path) -> str:
    """Compute SHA-256 of file contents, prefixed with 'sha256:'."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def _should_exclude(path: Path, exclude_set: frozenset[str]) -> bool:
    """Check if any path component matches an exclude pattern."""
    for part in path.parts:
        if part in exclude_set:
            return True
    return False


def scan_paths(
    paths: list[str],
    *,
    exclude_patterns: list[str] | None = None,
    extensions: list[str] | None = None,
) -> list[dict]:
    """Scan paths and return sorted list of file records.

    Args:
        paths: File or directory paths to scan.
        exclude_patterns: Directory/file names to skip (added to defaults).
        extensions: If set, only include files with these extensions (e.g. [".py", ".md"]).

    Returns:
        Sorted list of dicts with keys: path, size, hash.

    Raises:
        FileNotFoundError: If any provided path does not exist.
    """
    excludes = set(_DEFAULT_EXCLUDES)
    if exclude_patterns:
        excludes.update(exclude_patterns)
    excludes_frozen = frozenset(excludes)

    results: list[dict] = []

    for raw_path in paths:
        p = Path(raw_path)
        if not p.exists():
            raise FileNotFoundError(f"Path not found: {p}")

        if p.is_file():
            if extensions and p.suffix not in extensions:
                continue
            if not _should_exclude(p, excludes_frozen):
                results.append({
                    "path": str(p),
                    "size": p.stat().st_size,
                    "hash": _hash_file(p),
                })
        elif p.is_dir():
            for child in sorted(p.rglob("*")):
                if not child.is_file():
                    continue
                if _should_exclude(child, excludes_frozen):
                    continue
                if extensions and child.suffix not in extensions:
                    continue
                results.append({
                    "path": str(child),
                    "size": child.stat().st_size,
                    "hash": _hash_file(child),
                })

    # Sort by path for deterministic output.
    results.sort(key=lambda r: r["path"])
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Enumerate files with content hashes for review coverage."
    )
    parser.add_argument(
        "paths", nargs="+",
        help="Files or directories to scan.",
    )
    parser.add_argument(
        "--exclude", nargs="+", default=None,
        help="Additional directory/file names to exclude.",
    )
    parser.add_argument(
        "--ext", nargs="+", default=None,
        help="Only include files with these extensions (e.g. .py .md).",
    )

    args = parser.parse_args(argv)
    results = scan_paths(
        args.paths,
        exclude_patterns=args.exclude,
        extensions=args.ext,
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
