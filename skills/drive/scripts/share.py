# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-api-python-client",
#     "google-auth",
#     "google-auth-httplib2",
#     "keyring",
# ]
# ///
"""Manage file sharing permissions on Google Drive.

Usage:
    uv run share.py share --file-id ID --email EMAIL --role ROLE
    uv run share.py list  --file-id ID
    uv run share.py remove --file-id ID --email EMAIL
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from auth import get_drive_service
from contracts import precondition, ContractViolationError


@precondition(lambda file_id, **kw: file_id and file_id.strip(), "file_id must be non-empty")
def share_file(
    file_id: str,
    email: str = "",
    role: str = "reader",
) -> dict:
    """Share a file with a specific user.

    Args:
        file_id: Google Drive file ID.
        email: Email address of the user.
        role: Permission role (reader, commenter, writer, organizer).

    Returns:
        Dict with permission metadata.
    """
    service = get_drive_service()

    result = service.permissions().create(
        fileId=file_id,
        body={
            "type": "user",
            "role": role,
            "emailAddress": email,
        },
        supportsAllDrives=True,
        sendNotificationEmail=True,
        fields="id, role, type, emailAddress",
    ).execute()

    print(f"Shared with {email} as {role}")
    return result


@precondition(lambda file_id, **kw: file_id and file_id.strip(), "file_id must be non-empty")
def list_permissions(file_id: str) -> list[dict]:
    """List all permissions on a file.

    Args:
        file_id: Google Drive file ID.

    Returns:
        List of permission dicts.
    """
    service = get_drive_service()

    result = service.permissions().list(
        fileId=file_id,
        supportsAllDrives=True,
        fields="permissions(id, role, type, emailAddress, displayName)",
    ).execute()

    perms = result.get("permissions", [])
    for p in perms:
        print(f"  {p.get('emailAddress', 'N/A')} — {p.get('role', 'unknown')} ({p.get('type', 'unknown')})")
    return perms


@precondition(lambda file_id, **kw: file_id and file_id.strip(), "file_id must be non-empty")
@precondition(lambda file_id, email, **kw: email and email.strip(), "email must be non-empty")
def remove_permission(file_id: str, email: str) -> None:
    """Remove a user's permission from a file.

    Args:
        file_id: Google Drive file ID.
        email: Email address of the user to remove.
    """
    service = get_drive_service()

    # Find permission by email
    perms = service.permissions().list(
        fileId=file_id,
        supportsAllDrives=True,
        fields="permissions(id, emailAddress)",
    ).execute().get("permissions", [])

    for p in perms:
        if p.get("emailAddress", "").lower() == email.lower():
            service.permissions().delete(
                fileId=file_id,
                permissionId=p["id"],
                supportsAllDrives=True,
            ).execute()
            print(f"Removed permission for {email}")
            return

    print(f"No permission found for {email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage file sharing")
    sub = parser.add_subparsers(dest="action")

    share_p = sub.add_parser("share", help="Share a file")
    share_p.add_argument("--file-id", required=True)
    share_p.add_argument("--email", required=True)
    share_p.add_argument("--role", default="reader", choices=["reader", "commenter", "writer", "organizer"])

    list_p = sub.add_parser("list", help="List permissions")
    list_p.add_argument("--file-id", required=True)

    remove_p = sub.add_parser("remove", help="Remove a permission")
    remove_p.add_argument("--file-id", required=True)
    remove_p.add_argument("--email", required=True)

    args = parser.parse_args()

    if args.action == "share":
        share_file(file_id=args.file_id, email=args.email, role=args.role)
    elif args.action == "list":
        list_permissions(file_id=args.file_id)
    elif args.action == "remove":
        remove_permission(file_id=args.file_id, email=args.email)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
