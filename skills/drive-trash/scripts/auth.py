# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-auth",
#     "google-auth-httplib2",
#     "google-api-python-client",
#     "keyring",
# ]
# ///
"""Authentication module for Google Drive trash skill.

Reads OAuth credentials from macOS Keychain, builds google-auth
Credentials objects, and auto-refreshes expired tokens.

Shares the same Keychain service as the drive skill.
"""
from __future__ import annotations

import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from contracts import ContractViolationError, precondition, postcondition

KEYCHAIN_SERVICE = "claude-skill-google-drive"
TOKEN_URI = "https://oauth2.googleapis.com/token"

CREDENTIAL_KEYS = ("client_id", "client_secret", "refresh_token", "access_token", "token_expiry")


def _read_keychain(key: str) -> str | None:
    """Read a single value from the Keychain."""
    return keyring.get_password(KEYCHAIN_SERVICE, key)


def get_credentials() -> Credentials:
    """Load OAuth credentials from macOS Keychain, refreshing if expired.

    Returns a valid google.oauth2.credentials.Credentials object.

    Raises:
        ContractViolationError: if no refresh_token is stored (not authenticated).
    """
    refresh_token = _read_keychain("refresh_token")
    if not refresh_token:
        raise ContractViolationError(
            "Not authenticated. Run setup_auth.py from the drive skill first.", kind="precondition"
        )

    client_id = _read_keychain("client_id")
    client_secret = _read_keychain("client_secret")
    access_token = _read_keychain("access_token")

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri=TOKEN_URI,
    )

    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        keyring.set_password(KEYCHAIN_SERVICE, "access_token", creds.token or "")
        expiry_str = creds.expiry.isoformat() if creds.expiry else ""
        keyring.set_password(KEYCHAIN_SERVICE, "token_expiry", expiry_str)

    return creds


def get_drive_service():
    """Build and return a Google Drive v3 API service object."""
    creds = get_credentials()
    return build("drive", "v3", credentials=creds)


def store_credentials(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    access_token: str,
    token_expiry: str,
) -> None:
    """Store all OAuth credential components in macOS Keychain.

    Included for import compatibility when running combined test suites.
    Auth setup is done through the main drive skill.
    """
    keyring.set_password(KEYCHAIN_SERVICE, "client_id", client_id)
    keyring.set_password(KEYCHAIN_SERVICE, "client_secret", client_secret)
    keyring.set_password(KEYCHAIN_SERVICE, "refresh_token", refresh_token)
    keyring.set_password(KEYCHAIN_SERVICE, "access_token", access_token)
    keyring.set_password(KEYCHAIN_SERVICE, "token_expiry", token_expiry)
