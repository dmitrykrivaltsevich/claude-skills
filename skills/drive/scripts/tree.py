# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-api-python-client",
#     "google-auth",
#     "google-auth-httplib2",
#     "keyring",
# ]
# ///
"""Recursively list Google Drive folder tree.

Usage:
    uv run tree.py [--folder-id ID] [--depth N] [--name-filter TEXT]
"""
from __future__ import annotations

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from auth import get_drive_service
from contracts import precondition

FOLDER_MIME = "application/vnd.google-apps.folder"
FIELDS = "files(id, name, mimeType, modifiedTime, size)"


@precondition(lambda depth, **kw: depth >= 1, "depth must be >= 1")
def list_tree(
    folder_id: str | None = None,
    depth: int = 3,
    name_filter: str | None = None,
) -> list[dict]:
    """Recursively list folder contents up to a given depth.

    Each returned item includes 'path' (relative from starting folder)
    and 'depth' (0-indexed level from start).

    When name_filter is provided, only items whose name contains the
    filter text (case-insensitive) are included in results, but ALL
    folders are still traversed to find deep matches.

    Args:
        folder_id: Starting folder ID. Defaults to root.
        depth: Maximum depth to recurse (1 = root only, 2 = root + children, etc.)
        name_filter: Optional case-insensitive substring filter on item names.

    Returns:
        Flat list of item dicts with added 'path' and 'depth' fields.
    """
    service = get_drive_service()
    results: list[dict] = []
    _filter_lower = name_filter.lower() if name_filter else None

    def _recurse(parent_id: str, current_depth: int, path_prefix: str) -> None:
        q = f"'{parent_id}' in parents and trashed = false"
        items = service.files().list(
            q=q,
            pageSize=1000,
            fields=FIELDS,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute().get("files", [])

        for item in items:
            item_path = f"{path_prefix}/{item['name']}" if path_prefix else item["name"]
            is_folder = item.get("mimeType") == FOLDER_MIME

            # Check name filter
            matches_filter = (
                _filter_lower is None
                or _filter_lower in item["name"].lower()
            )

            if matches_filter:
                results.append({
                    **item,
                    "path": item_path,
                    "depth": current_depth,
                })

            # Recurse into folders regardless of filter match (to find deep matches)
            if is_folder and current_depth + 1 < depth:
                _recurse(item["id"], current_depth + 1, item_path)

    parent = folder_id or "root"
    _recurse(parent, 0, "")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="List Google Drive folder tree")
    parser.add_argument("--folder-id", help="Starting folder ID (default: root)")
    parser.add_argument("--depth", type=int, default=3, help="Max traversal depth (default: 3)")
    parser.add_argument("--name-filter", help="Case-insensitive name substring filter")
    args = parser.parse_args()

    items = list_tree(
        folder_id=args.folder_id,
        depth=args.depth,
        name_filter=args.name_filter,
    )

    for item in items:
        is_folder = item.get("mimeType") == FOLDER_MIME
        indent = "  " * item["depth"]
        icon = "📁" if is_folder else "📄"
        print(f"{indent}{icon} {item['path']}  (id: {item['id']})")

    if not items:
        print("No items found.")
    else:
        print(f"\n{len(items)} item(s) found.")


if __name__ == "__main__":
    main()
