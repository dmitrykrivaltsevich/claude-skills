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
    uv run search.py --query TEXT [--name-only] [--mime-type TYPE] [--folder-id ID] [--shared-drives-only]
    uv run search.py --q "raw Drive API query string"
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
    name_only: bool = False,
    page_size: int = 100,
) -> list[dict]:
    """Search for files in Google Drive.

    By default, searches both file/folder names AND full-text content.
    Use name_only=True to restrict to name matching only (useful for
    finding folders or files by title without content indexing noise).

    Args:
        query: Search query text.
        mime_type: Filter by MIME type.
        folder_id: Restrict search to a specific folder.
        shared_drives_only: Only search shared drives.
        name_only: If True, search only by name (not full-text content).
        page_size: Max results per page.

    Returns:
        List of file metadata dicts.
    """
    service = get_drive_service()

    escaped = query.replace("'", "\\'")

    if name_only:
        q_parts = [f"name contains '{escaped}'"]
    else:
        q_parts = [f"(fullText contains '{escaped}' or name contains '{escaped}')"]

    if mime_type:
        q_parts.append(f"mimeType = '{mime_type}'")
    if folder_id:
        q_parts.append(f"'{folder_id}' in parents")
    q_parts.append("trashed = false")

    q_string = " and ".join(q_parts)

    kwargs = {
        "q": q_string,
        "pageSize": page_size,
        "fields": f"nextPageToken, {FIELDS}",
        "supportsAllDrives": True,
        "includeItemsFromAllDrives": True,
    }

    if shared_drives_only:
        kwargs["corpora"] = "allDrives"

    all_files: list[dict] = []
    while True:
        response = service.files().list(**kwargs).execute()
        all_files.extend(response.get("files", []))
        token = response.get("nextPageToken")
        if not token:
            break
        kwargs["pageToken"] = token

    return all_files


@precondition(lambda q, **kw: q and q.strip(), "q must be non-empty")
def query_drive(
    q: str,
    page_size: int = 100,
) -> list[dict]:
    """Execute a raw Google Drive API query.

    The query string is passed directly to the Drive API files.list()
    endpoint without any wrapping or escaping. The caller (LLM) is
    responsible for constructing a valid query using the Drive API
    query syntax.

    Reference: https://developers.google.com/drive/api/guides/search-files

    Args:
        q: Raw Drive API query string.
        page_size: Max results per page.

    Returns:
        List of file metadata dicts.
    """
    service = get_drive_service()

    kwargs = {
        "q": q,
        "pageSize": page_size,
        "fields": f"nextPageToken, {FIELDS}",
        "supportsAllDrives": True,
        "includeItemsFromAllDrives": True,
    }

    all_files: list[dict] = []
    while True:
        response = service.files().list(**kwargs).execute()
        all_files.extend(response.get("files", []))
        token = response.get("nextPageToken")
        if not token:
            break
        kwargs["pageToken"] = token

    return all_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Search Google Drive")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--query", help="Search query text (convenience: searches name + content)")
    group.add_argument("--q", dest="raw_q", help="Raw Drive API query string (passed directly, no wrapping)")

    parser.add_argument("--name-only", action="store_true", help="Search by name only (only with --query)")
    parser.add_argument("--mime-type", help="Filter by MIME type (only with --query)")
    parser.add_argument("--folder-id", help="Restrict to folder ID (only with --query)")
    parser.add_argument("--shared-drives-only", action="store_true")
    parser.add_argument("--page-size", type=int, default=100)
    args = parser.parse_args()

    if args.raw_q:
        results = query_drive(
            q=args.raw_q,
            page_size=args.page_size,
        )
    else:
        results = search_files(
            query=args.query,
            mime_type=args.mime_type,
            folder_id=args.folder_id,
            shared_drives_only=args.shared_drives_only,
            name_only=args.name_only,
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
