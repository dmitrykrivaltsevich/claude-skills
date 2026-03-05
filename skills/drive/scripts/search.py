# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-api-python-client",
#     "google-auth",
#     "google-auth-httplib2",
#     "keyring",
# ]
# ///
"""Search Google Drive files and folders.

Usage:
    uv run search.py --query TEXT [--mime-type TYPE] [--folder-id ID] [--shared-drives-only]
"""
from __future__ import annotations

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from auth import get_drive_service
from contracts import precondition, ContractViolationError

FIELDS = "files(id, name, mimeType, modifiedTime, size, parents, owners, driveId, webViewLink)"


@precondition(lambda query, **kw: query and query.strip(), "query must be non-empty")
def search_files(
    query: str,
    mime_type: str | None = None,
    folder_id: str | None = None,
    shared_drives_only: bool = False,
    page_size: int = 100,
) -> list[dict]:
    """Search for files in Google Drive.

    Args:
        query: Full-text search query.
        mime_type: Filter by MIME type.
        folder_id: Restrict search to a specific folder.
        shared_drives_only: Only search shared drives.
        page_size: Max results per page.

    Returns:
        List of file metadata dicts.
    """
    service = get_drive_service()

    q_parts = [f"fullText contains '{query}'"]
    if mime_type:
        q_parts.append(f"mimeType = '{mime_type}'")
    if folder_id:
        q_parts.append(f"'{folder_id}' in parents")
    q_parts.append("trashed = false")

    q_string = " and ".join(q_parts)

    kwargs = {
        "q": q_string,
        "pageSize": page_size,
        "fields": FIELDS,
        "supportsAllDrives": True,
        "includeItemsFromAllDrives": True,
    }

    if shared_drives_only:
        kwargs["corpora"] = "allDrives"

    results = service.files().list(**kwargs).execute()
    return results.get("files", [])


def main() -> None:
    parser = argparse.ArgumentParser(description="Search Google Drive")
    parser.add_argument("--query", required=True, help="Search query text")
    parser.add_argument("--mime-type", help="Filter by MIME type")
    parser.add_argument("--folder-id", help="Restrict to folder ID")
    parser.add_argument("--shared-drives-only", action="store_true")
    parser.add_argument("--page-size", type=int, default=100)
    args = parser.parse_args()

    results = search_files(
        query=args.query,
        mime_type=args.mime_type,
        folder_id=args.folder_id,
        shared_drives_only=args.shared_drives_only,
        page_size=args.page_size,
    )

    for f in results:
        print(f"  {f['name']}  (id: {f['id']}, type: {f.get('mimeType', 'unknown')})")

    if not results:
        print("No files found.")
    else:
        print(f"\n{len(results)} file(s) found.")


if __name__ == "__main__":
    main()
