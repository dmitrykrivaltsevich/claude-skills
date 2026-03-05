# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-api-python-client",
#     "google-auth",
#     "google-auth-httplib2",
#     "keyring",
# ]
# ///
"""List available Shared Drives.

Usage:
    uv run list_drives.py [--page-size N]
"""
from __future__ import annotations

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from auth import get_drive_service


def list_shared_drives(page_size: int = 100) -> list[dict]:
    """List all Shared Drives accessible to the authenticated user.

    Args:
        page_size: Max results per page.

    Returns:
        List of Shared Drive metadata dicts (id, name, etc.).
    """
    service = get_drive_service()

    kwargs = {
        "pageSize": page_size,
        "fields": "nextPageToken, drives(id, name, createdTime)",
    }

    all_drives: list[dict] = []
    while True:
        response = service.drives().list(**kwargs).execute()
        all_drives.extend(response.get("drives", []))
        token = response.get("nextPageToken")
        if not token:
            break
        kwargs["pageToken"] = token

    return all_drives


def main() -> None:
    parser = argparse.ArgumentParser(description="List available Shared Drives")
    parser.add_argument("--page-size", type=int, default=100)
    args = parser.parse_args()

    drives = list_shared_drives(page_size=args.page_size)

    for d in drives:
        print(f"  📁 {d['name']}  (id: {d['id']})")

    if not drives:
        print("No Shared Drives found.")
    else:
        print(f"\n{len(drives)} Shared Drive(s).")


if __name__ == "__main__":
    main()
