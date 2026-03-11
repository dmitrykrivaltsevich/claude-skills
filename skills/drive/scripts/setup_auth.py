# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-auth",
#     "google-auth-oauthlib",
#     "google-auth-httplib2",
#     "google-api-python-client",
#     "keyring",
# ]
# ///
"""Setup Google Drive OAuth authentication.

Runs the browser-based OAuth flow and stores credentials in macOS Keychain.

Usage:
    uv run setup_auth.py --client-id CLIENT_ID --client-secret CLIENT_SECRET
"""
from __future__ import annotations

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from google_auth_oauthlib.flow import InstalledAppFlow

from auth import store_credentials

SCOPES = ["https://www.googleapis.com/auth/drive"]


def main(client_id: str, client_secret: str) -> None:
    """Run OAuth flow and store credentials.

    Args:
        client_id: Google OAuth client ID.
        client_secret: Google OAuth client secret.

    Raises:
        ValueError: if client_id or client_secret is empty.
    """
    if not client_id or not client_id.strip():
        raise ValueError("client_id must be non-empty")
    if not client_secret or not client_secret.strip():
        raise ValueError("client_secret must be non-empty")

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    token_expiry = creds.expiry.isoformat() if creds.expiry else ""

    store_credentials(
        client_id=creds.client_id,
        client_secret=creds.client_secret,
        refresh_token=creds.refresh_token,
        access_token=creds.token,
        token_expiry=token_expiry,
    )

    print("SUCCESS: Google Drive authentication complete. Credentials stored in macOS Keychain.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup Google Drive OAuth")
    parser.add_argument("--client-id", required=True, help="OAuth client ID")
    parser.add_argument("--client-secret", required=True, help="OAuth client secret")
    args = parser.parse_args()
    main(client_id=args.client_id, client_secret=args.client_secret)
