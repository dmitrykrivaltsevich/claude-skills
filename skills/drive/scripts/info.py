# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-api-python-client",
#     "google-auth",
#     "google-auth-httplib2",
#     "keyring",
# ]
# ///
"""Get detailed file metadata from Google Drive.

Usage:
    uv run info.py --file-id ID
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from auth import get_drive_service
from contracts import precondition, ContractViolationError

INFO_FIELDS = (
    "id, name, mimeType, createdTime, modifiedTime, size, "
    "owners, lastModifyingUser, description, starred, "
    "parents, webViewLink, webContentLink, trashed, "
    "driveId, capabilities, sharingUser, shared"
)


@precondition(lambda file_id, **kw: file_id and file_id.strip(), "file_id must be non-empty")
def get_file_info(file_id: str) -> dict:
    """Get detailed metadata for a Google Drive file.

    Args:
        file_id: Google Drive file ID.

    Returns:
        Dict with comprehensive file metadata.
    """
    service = get_drive_service()

    result = service.files().get(
        fileId=file_id,
        fields=INFO_FIELDS,
        supportsAllDrives=True,
    ).execute()

    print(json.dumps(result, indent=2, default=str))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Google Drive file info")
    parser.add_argument("--file-id", required=True, help="File ID")
    args = parser.parse_args()

    get_file_info(file_id=args.file_id)


if __name__ == "__main__":
    main()
