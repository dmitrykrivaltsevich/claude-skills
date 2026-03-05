# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-api-python-client",
#     "google-auth",
#     "google-auth-httplib2",
#     "keyring",
# ]
# ///
"""Update file metadata: rename, move, star, set description.

Usage:
    uv run update.py --file-id ID [--name NAME] [--move-to FOLDER_ID] [--star] [--description TEXT]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from auth import get_drive_service
from contracts import precondition, ContractViolationError


@precondition(lambda file_id, **kw: file_id and file_id.strip(), "file_id must be non-empty")
def update_file(
    file_id: str,
    name: str | None = None,
    move_to: str | None = None,
    star: bool | None = None,
    description: str | None = None,
) -> dict:
    """Update file metadata on Google Drive.

    Args:
        file_id: Google Drive file ID.
        name: New name for the file.
        move_to: Folder ID to move the file to.
        star: If True, star the file; if False, unstar.
        description: New description for the file.

    Returns:
        Dict with updated file metadata.
    """
    service = get_drive_service()

    body: dict = {}
    kwargs: dict = {
        "fileId": file_id,
        "supportsAllDrives": True,
        "fields": "id, name, mimeType, modifiedTime, starred, description, parents",
    }

    if name is not None:
        body["name"] = name
    if star is not None:
        body["starred"] = star
    if description is not None:
        body["description"] = description

    if move_to:
        # Get current parents to remove
        current = service.files().get(
            fileId=file_id,
            fields="parents",
            supportsAllDrives=True,
        ).execute()
        current_parents = ",".join(current.get("parents", []))
        kwargs["addParents"] = move_to
        kwargs["removeParents"] = current_parents

    kwargs["body"] = body

    result = service.files().update(**kwargs).execute()
    print(f"Updated: {result.get('name', file_id)} (id: {result.get('id', file_id)})")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Update Google Drive file metadata")
    parser.add_argument("--file-id", required=True, help="File ID")
    parser.add_argument("--name", help="New file name")
    parser.add_argument("--move-to", help="Destination folder ID")
    parser.add_argument("--star", action="store_true", default=None, help="Star the file")
    parser.add_argument("--description", help="New description")
    args = parser.parse_args()

    update_file(
        file_id=args.file_id,
        name=args.name,
        move_to=args.move_to,
        star=args.star,
        description=args.description,
    )


if __name__ == "__main__":
    main()
