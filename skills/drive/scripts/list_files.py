# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-api-python-client",
#     "google-auth",
#     "google-auth-httplib2",
#     "keyring",
# ]
# ///
"""List files in a Google Drive folder.

Usage:
    uv run list_files.py [--folder-id ID] [--page-size N] [--order-by FIELD]
"""
from __future__ import annotations

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from auth import get_drive_service

FIELDS = "files(id, name, mimeType, modifiedTime, size, parents, owners, webViewLink)"


def list_folder(
    folder_id: str | None = None,
    page_size: int = 100,
    order_by: str = "modifiedTime desc",
) -> list[dict]:
    """List files in a Google Drive folder.

    Args:
        folder_id: Folder ID to list. Defaults to root.
        page_size: Max results per page.
        order_by: Sort order field.

    Returns:
        List of file metadata dicts.
    """
    service = get_drive_service()

    parent = folder_id or "root"
    q = f"'{parent}' in parents and trashed = false"

    results = service.files().list(
        q=q,
        pageSize=page_size,
        fields=FIELDS,
        orderBy=order_by,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    return results.get("files", [])


def main() -> None:
    parser = argparse.ArgumentParser(description="List Google Drive folder contents")
    parser.add_argument("--folder-id", help="Folder ID (default: root)")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--order-by", default="modifiedTime desc")
    args = parser.parse_args()

    files = list_folder(
        folder_id=args.folder_id,
        page_size=args.page_size,
        order_by=args.order_by,
    )

    for f in files:
        kind = "📁" if f.get("mimeType") == "application/vnd.google-apps.folder" else "📄"
        print(f"  {kind} {f['name']}  (id: {f['id']})")

    if not files:
        print("Folder is empty.")
    else:
        print(f"\n{len(files)} item(s).")


if __name__ == "__main__":
    main()
