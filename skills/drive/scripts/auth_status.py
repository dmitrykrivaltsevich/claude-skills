# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-auth",
#     "google-auth-httplib2",
#     "google-api-python-client",
#     "keyring",
# ]
# ///
"""Check Google Drive authentication status.

Outputs AUTHENTICATED or NOT_AUTHENTICATED to stdout.
Used by SKILL.md dynamic context injection.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import keyring
from contracts import ContractViolationError

KEYCHAIN_SERVICE = "claude-skill-google-drive"


def main() -> None:
    """Check authentication status and print result."""
    refresh_token = keyring.get_password(KEYCHAIN_SERVICE, "refresh_token")

    if not refresh_token:
        print("NOT_AUTHENTICATED: No credentials found. Guide user through setup.")
        return

    try:
        from auth import get_drive_service

        service = get_drive_service()

        # Use Drive about endpoint — always works with Drive scope
        try:
            about = service.about().get(fields="user(emailAddress, displayName)").execute()
            user = about.get("user", {})
            email = user.get("emailAddress", "unknown")
        except Exception:
            email = "unknown"

        print(f"AUTHENTICATED: {email}")

    except Exception as e:
        print(f"NOT_AUTHENTICATED: {e}")


if __name__ == "__main__":
    main()
