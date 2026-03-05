# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "pytest-mock"]
# ///
"""Tests for auth module — credential management via macOS Keychain."""
import json
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from contracts import ContractViolationError


KEYCHAIN_SERVICE = "claude-skill-google-drive"


class TestGetCredentials:
    """Test get_credentials() reads from Keychain and builds Credentials object."""

    @patch("auth.keyring")
    @patch("auth.Credentials")
    def test_returns_credentials_from_keychain(self, mock_creds_cls, mock_keyring):
        from auth import get_credentials

        mock_keyring.get_password.side_effect = lambda svc, key: {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "refresh_token": "test-refresh-token",
            "access_token": "test-access-token",
            "token_expiry": "2026-12-31T00:00:00Z",
        }.get(key)

        mock_cred = MagicMock()
        mock_cred.valid = True
        mock_cred.expired = False
        mock_creds_cls.return_value = mock_cred

        result = get_credentials()
        assert result is mock_cred
        mock_creds_cls.assert_called_once_with(
            token="test-access-token",
            refresh_token="test-refresh-token",
            client_id="test-client-id",
            client_secret="test-client-secret",
            token_uri="https://oauth2.googleapis.com/token",
        )

    @patch("auth.keyring")
    def test_raises_when_no_refresh_token(self, mock_keyring):
        from auth import get_credentials

        mock_keyring.get_password.return_value = None

        with pytest.raises(ContractViolationError, match="Not authenticated"):
            get_credentials()

    @patch("auth.keyring")
    @patch("auth.Credentials")
    @patch("auth.Request")
    def test_refreshes_expired_token(self, mock_request_cls, mock_creds_cls, mock_keyring):
        from auth import get_credentials

        mock_keyring.get_password.side_effect = lambda svc, key: {
            "client_id": "cid",
            "client_secret": "csec",
            "refresh_token": "rt",
            "access_token": "old-at",
            "token_expiry": "2020-01-01T00:00:00Z",
        }.get(key)

        mock_cred = MagicMock()
        mock_cred.valid = False
        mock_cred.expired = True
        mock_cred.refresh_token = "rt"
        mock_cred.token = "new-at"
        mock_cred.expiry = None
        mock_creds_cls.return_value = mock_cred

        result = get_credentials()
        mock_cred.refresh.assert_called_once()

    @patch("auth.keyring")
    @patch("auth.Credentials")
    @patch("auth.Request")
    def test_stores_refreshed_token_back_to_keychain(self, mock_request_cls, mock_creds_cls, mock_keyring):
        from auth import get_credentials

        mock_keyring.get_password.side_effect = lambda svc, key: {
            "client_id": "cid",
            "client_secret": "csec",
            "refresh_token": "rt",
            "access_token": "old",
            "token_expiry": "2020-01-01T00:00:00Z",
        }.get(key)

        mock_cred = MagicMock()
        mock_cred.valid = False
        mock_cred.expired = True
        mock_cred.refresh_token = "rt"
        mock_cred.token = "refreshed-token"
        mock_cred.expiry = None
        mock_creds_cls.return_value = mock_cred

        get_credentials()

        # Should store updated access_token back
        calls = mock_keyring.set_password.call_args_list
        stored_keys = {c[0][1] for c in calls}
        assert "access_token" in stored_keys


class TestGetDriveService:
    """Test get_drive_service() builds a Drive v3 service."""

    @patch("auth.build")
    @patch("auth.get_credentials")
    def test_builds_drive_v3_service(self, mock_get_creds, mock_build):
        from auth import get_drive_service

        mock_cred = MagicMock()
        mock_get_creds.return_value = mock_cred
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        result = get_drive_service()
        assert result is mock_service
        mock_build.assert_called_once_with("drive", "v3", credentials=mock_cred)

    @patch("auth.build")
    @patch("auth.get_credentials")
    def test_returns_non_none(self, mock_get_creds, mock_build):
        from auth import get_drive_service

        mock_get_creds.return_value = MagicMock()
        mock_build.return_value = MagicMock()

        result = get_drive_service()
        assert result is not None


class TestStoreCredentials:
    """Test store_credentials() writes to Keychain."""

    @patch("auth.keyring")
    def test_stores_all_fields(self, mock_keyring):
        from auth import store_credentials

        store_credentials(
            client_id="cid",
            client_secret="csec",
            refresh_token="rt",
            access_token="at",
            token_expiry="2026-12-31T00:00:00Z",
        )

        assert mock_keyring.set_password.call_count == 5
        stored = {c[0][1]: c[0][2] for c in mock_keyring.set_password.call_args_list}
        assert stored["client_id"] == "cid"
        assert stored["client_secret"] == "csec"
        assert stored["refresh_token"] == "rt"
        assert stored["access_token"] == "at"
        assert stored["token_expiry"] == "2026-12-31T00:00:00Z"

    @patch("auth.keyring")
    def test_all_under_correct_service(self, mock_keyring):
        from auth import store_credentials

        store_credentials(
            client_id="c", client_secret="s",
            refresh_token="r", access_token="a", token_expiry="t",
        )

        for call in mock_keyring.set_password.call_args_list:
            assert call[0][0] == KEYCHAIN_SERVICE
