# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "pytest-mock"]
# ///
"""Tests for auth_status module."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock
from io import StringIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestAuthStatus:
    """Test auth_status.py main() output."""

    @patch("auth_status.keyring")
    def test_not_authenticated_when_no_refresh_token(self, mock_keyring, capsys):
        from auth_status import main

        mock_keyring.get_password.return_value = None
        main()
        captured = capsys.readouterr()
        assert "NOT_AUTHENTICATED" in captured.out

    @patch("auth_status.keyring")
    def test_authenticated_when_valid_credentials(self, mock_keyring, capsys):
        from auth_status import main

        mock_keyring.get_password.side_effect = lambda svc, key: {
            "refresh_token": "rt",
        }.get(key)

        mock_cred = MagicMock()
        mock_cred.valid = True
        mock_cred.token = "at"

        with patch("auth.get_credentials", return_value=mock_cred), \
             patch("googleapiclient.discovery.build") as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            mock_service.userinfo().get().execute.return_value = {"email": "user@example.com"}

            main()

        captured = capsys.readouterr()
        assert "AUTHENTICATED" in captured.out

    @patch("auth_status.keyring")
    def test_not_authenticated_on_refresh_failure(self, mock_keyring, capsys):
        from auth_status import main

        mock_keyring.get_password.side_effect = lambda svc, key: {
            "refresh_token": "rt",
        }.get(key)

        with patch("auth.get_credentials", side_effect=Exception("refresh failed")):
            main()

        captured = capsys.readouterr()
        assert "NOT_AUTHENTICATED" in captured.out
