# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest",
#     "pytest-mock",
#     "keyring",
#     "google-api-python-client",
#     "google-auth",
#     "google-auth-httplib2",
#     "google-auth-oauthlib",
# ]
# ///
"""Tests for setup_auth module."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestSetupAuth:
    """Test setup_auth.py main() flow."""

    @patch("setup_auth.store_credentials")
    @patch("setup_auth.InstalledAppFlow")
    def test_runs_oauth_flow_and_stores_credentials(self, mock_flow_cls, mock_store):
        from setup_auth import main

        mock_flow = MagicMock()
        mock_flow_cls.from_client_config.return_value = mock_flow

        mock_creds = MagicMock()
        mock_creds.refresh_token = "test-refresh-token"
        mock_creds.token = "test-access-token"
        mock_creds.client_id = "test-cid"
        mock_creds.client_secret = "test-csec"
        mock_creds.expiry = None
        mock_flow.run_local_server.return_value = mock_creds

        main(client_id="test-cid", client_secret="test-csec")

        mock_flow_cls.from_client_config.assert_called_once()
        config = mock_flow_cls.from_client_config.call_args[0][0]
        assert config["installed"]["client_id"] == "test-cid"
        assert config["installed"]["client_secret"] == "test-csec"

        mock_flow.run_local_server.assert_called_once_with(port=0)

        mock_store.assert_called_once_with(
            client_id="test-cid",
            client_secret="test-csec",
            refresh_token="test-refresh-token",
            access_token="test-access-token",
            token_expiry="",
        )

    @patch("setup_auth.store_credentials")
    @patch("setup_auth.InstalledAppFlow")
    def test_stores_token_expiry_as_iso(self, mock_flow_cls, mock_store):
        from setup_auth import main
        from datetime import datetime, timezone

        mock_flow = MagicMock()
        mock_flow_cls.from_client_config.return_value = mock_flow

        expiry = datetime(2026, 12, 31, 0, 0, 0, tzinfo=timezone.utc)
        mock_creds = MagicMock()
        mock_creds.refresh_token = "rt"
        mock_creds.token = "at"
        mock_creds.client_id = "cid"
        mock_creds.client_secret = "csec"
        mock_creds.expiry = expiry
        mock_flow.run_local_server.return_value = mock_creds

        main(client_id="cid", client_secret="csec")

        stored_expiry = mock_store.call_args[1]["token_expiry"]
        assert "2026-12-31" in stored_expiry

    @patch("setup_auth.store_credentials")
    @patch("setup_auth.InstalledAppFlow")
    def test_uses_drive_scope(self, mock_flow_cls, mock_store):
        from setup_auth import main

        mock_flow = MagicMock()
        mock_flow_cls.from_client_config.return_value = mock_flow
        mock_creds = MagicMock()
        mock_creds.refresh_token = "rt"
        mock_creds.token = "at"
        mock_creds.client_id = "cid"
        mock_creds.client_secret = "csec"
        mock_creds.expiry = None
        mock_flow.run_local_server.return_value = mock_creds

        main(client_id="cid", client_secret="csec")

        scopes = mock_flow_cls.from_client_config.call_args[0][1]
        assert "https://www.googleapis.com/auth/drive" in scopes

    def test_raises_on_missing_client_id(self):
        from setup_auth import main

        with pytest.raises((ValueError, TypeError)):
            main(client_id="", client_secret="csec")

    def test_raises_on_missing_client_secret(self):
        from setup_auth import main

        with pytest.raises((ValueError, TypeError)):
            main(client_id="cid", client_secret="")
