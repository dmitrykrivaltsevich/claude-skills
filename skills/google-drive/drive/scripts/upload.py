# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-api-python-client",
#     "google-auth",
#     "google-auth-httplib2",
#     "keyring",
# ]
# ///
"""Upload a local file to Google Drive.

Usage:
    uv run upload.py --file-path PATH [--folder-id ID] [--convert]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from googleapiclient.http import MediaFileUpload

from auth import get_drive_service
from contracts import precondition, ContractViolationError


@precondition(lambda file_path, **kw: file_path and file_path.strip(), "file_path must be non-empty")
@precondition(lambda file_path, **kw: os.path.exists(file_path), "file_path must exist")
def upload_file(
    file_path: str,
    folder_id: str | None = None,
    convert: bool = False,
) -> dict:
    """Upload a local file to Google Drive.

    Args:
        file_path: Absolute or relative path to the local file.
        folder_id: Optional parent folder ID in Drive.
        convert: If True, convert to Google Workspace format.

    Returns:
        Dict with uploaded file metadata.
    """
    service = get_drive_service()

    name = os.path.basename(file_path)
    body: dict = {"name": name}

    if folder_id:
        body["parents"] = [folder_id]

    media = MediaFileUpload(file_path, resumable=True)

    result = service.files().create(
        body=body,
        media_body=media,
        supportsAllDrives=True,
        fields="id, name, mimeType, webViewLink",
    ).execute()

    print(f"Uploaded: {result['name']} (id: {result['id']})")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload file to Google Drive")
    parser.add_argument("--file-path", required=True, help="Local file path")
    parser.add_argument("--folder-id", help="Parent folder ID")
    parser.add_argument("--convert", action="store_true", help="Convert to Google format")
    args = parser.parse_args()

    upload_file(file_path=args.file_path, folder_id=args.folder_id, convert=args.convert)


if __name__ == "__main__":
    main()
