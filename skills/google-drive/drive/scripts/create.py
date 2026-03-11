# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-api-python-client",
#     "google-auth",
#     "google-auth-httplib2",
#     "keyring",
# ]
# ///
"""Create a new Google Drive item (doc, sheet, slide, folder).

Usage:
    uv run create.py --name NAME --type TYPE [--folder-id ID]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from auth import get_drive_service
from contracts import precondition, ContractViolationError

ITEM_TYPE_MAP = {
    "doc": "application/vnd.google-apps.document",
    "sheet": "application/vnd.google-apps.spreadsheet",
    "slide": "application/vnd.google-apps.presentation",
    "folder": "application/vnd.google-apps.folder",
}


@precondition(lambda name, **kw: name and name.strip(), "name must be non-empty")
@precondition(
    lambda name, item_type, **kw: item_type in ITEM_TYPE_MAP,
    "item_type must be one of: doc, sheet, slide, folder",
)
def create_item(
    name: str,
    item_type: str,
    folder_id: str | None = None,
) -> dict:
    """Create a new Google Drive item.

    Args:
        name: Name of the new item.
        item_type: Type of item (doc, sheet, slide, folder).
        folder_id: Optional parent folder ID.

    Returns:
        Dict with created item metadata.
    """
    service = get_drive_service()

    body: dict = {
        "name": name,
        "mimeType": ITEM_TYPE_MAP[item_type],
    }

    if folder_id:
        body["parents"] = [folder_id]

    result = service.files().create(
        body=body,
        supportsAllDrives=True,
        fields="id, name, mimeType, webViewLink",
    ).execute()

    print(f"Created: {result['name']} (id: {result['id']}, type: {result.get('mimeType')})")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Google Drive item")
    parser.add_argument("--name", required=True, help="Item name")
    parser.add_argument(
        "--type", dest="item_type", required=True,
        choices=list(ITEM_TYPE_MAP.keys()),
        help="Item type",
    )
    parser.add_argument("--folder-id", help="Parent folder ID")
    args = parser.parse_args()

    create_item(name=args.name, item_type=args.item_type, folder_id=args.folder_id)


if __name__ == "__main__":
    main()
