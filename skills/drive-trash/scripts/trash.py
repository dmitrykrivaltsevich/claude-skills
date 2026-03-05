# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-api-python-client",
#     "google-auth",
#     "google-auth-httplib2",
#     "keyring",
# ]
# ///
"""Move a Google Drive file to trash (soft delete).

DANGER: This skill requires explicit user confirmation before execution.
The SKILL.md sets disable-model-invocation: true so Claude cannot
invoke this autonomously.

Usage:
    uv run trash.py --file-id ID
    uv run trash.py restore --file-id ID
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from auth import get_drive_service
from contracts import precondition, ContractViolationError


@precondition(lambda file_id, **kw: file_id and file_id.strip(), "file_id must be non-empty")
def trash_file(file_id: str) -> dict:
    """Move a file to trash.

    Args:
        file_id: Google Drive file ID.

    Returns:
        Dict with file metadata after trashing.
    """
    service = get_drive_service()

    # Verify file exists first
    meta = service.files().get(
        fileId=file_id,
        fields="id, name, mimeType, trashed",
        supportsAllDrives=True,
    ).execute()

    if meta.get("trashed"):
        print(f"File '{meta['name']}' is already in trash.")
        return meta

    result = service.files().update(
        fileId=file_id,
        body={"trashed": True},
        supportsAllDrives=True,
        fields="id, name, mimeType, trashed",
    ).execute()

    print(f"Moved to trash: {result['name']} (id: {result['id']})")
    return result


@precondition(lambda file_id, **kw: file_id and file_id.strip(), "file_id must be non-empty")
def restore_file(file_id: str) -> dict:
    """Restore a file from trash.

    Args:
        file_id: Google Drive file ID.

    Returns:
        Dict with file metadata after restoring.
    """
    service = get_drive_service()

    result = service.files().update(
        fileId=file_id,
        body={"trashed": False},
        supportsAllDrives=True,
        fields="id, name, mimeType, trashed",
    ).execute()

    print(f"Restored from trash: {result['name']} (id: {result['id']})")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Trash/restore Google Drive files")
    sub = parser.add_subparsers(dest="action")

    trash_p = sub.add_parser("trash", help="Move file to trash")
    trash_p.add_argument("--file-id", required=True, help="File ID")

    restore_p = sub.add_parser("restore", help="Restore file from trash")
    restore_p.add_argument("--file-id", required=True, help="File ID")

    args = parser.parse_args()

    if args.action == "trash":
        trash_file(file_id=args.file_id)
    elif args.action == "restore":
        restore_file(file_id=args.file_id)
    else:
        # Default: trash action with --file-id at top level
        parser.add_argument("--file-id", required=True, help="File ID to trash")
        args = parser.parse_args()
        trash_file(file_id=args.file_id)


if __name__ == "__main__":
    main()
