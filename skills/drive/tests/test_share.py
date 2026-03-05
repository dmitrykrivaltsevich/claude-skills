# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "pytest-mock"]
# ///
"""Tests for share.py — manage file permissions."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from contracts import ContractViolationError


class TestShare:
    def test_empty_file_id_raises(self):
        from share import share_file

        with pytest.raises(ContractViolationError):
            share_file(file_id="")

    @patch("share.get_drive_service")
    def test_adds_reader_permission(self, mock_svc_fn):
        from share import share_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.permissions().create().execute.return_value = {"id": "perm1"}

        result = share_file(file_id="f1", email="alice@example.com", role="reader")
        create_kwargs = mock_svc.permissions().create.call_args[1]
        assert create_kwargs["body"]["role"] == "reader"
        assert create_kwargs["body"]["emailAddress"] == "alice@example.com"

    @patch("share.get_drive_service")
    def test_lists_permissions(self, mock_svc_fn):
        from share import list_permissions

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.permissions().list().execute.return_value = {
            "permissions": [
                {"id": "p1", "role": "owner", "emailAddress": "owner@example.com"}
            ]
        }

        result = list_permissions(file_id="f1")
        assert len(result) == 1
        assert result[0]["role"] == "owner"

    @patch("share.get_drive_service")
    def test_removes_permission(self, mock_svc_fn):
        from share import remove_permission

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc

        # List to find permission by email
        mock_svc.permissions().list().execute.return_value = {
            "permissions": [
                {"id": "p1", "role": "reader", "emailAddress": "alice@example.com"}
            ]
        }
        mock_svc.permissions().delete().execute.return_value = None

        remove_permission(file_id="f1", email="alice@example.com")
        mock_svc.permissions().delete.assert_called()

    @patch("share.get_drive_service")
    def test_includes_shared_drives(self, mock_svc_fn):
        from share import share_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.permissions().create().execute.return_value = {"id": "p1"}

        share_file(file_id="f1", email="a@b.com", role="writer")
        create_kwargs = mock_svc.permissions().create.call_args[1]
        assert create_kwargs.get("supportsAllDrives") is True
