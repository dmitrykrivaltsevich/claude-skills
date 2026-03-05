# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "pytest-mock"]
# ///
"""Tests for info.py — get file metadata."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from contracts import ContractViolationError


class TestInfo:
    def test_empty_file_id_raises(self):
        from info import get_file_info

        with pytest.raises(ContractViolationError):
            get_file_info(file_id="")

    @patch("info.get_drive_service")
    def test_returns_file_metadata(self, mock_svc_fn):
        from info import get_file_info

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().get().execute.return_value = {
            "id": "f1",
            "name": "My Document",
            "mimeType": "application/vnd.google-apps.document",
            "createdTime": "2026-01-01T00:00:00Z",
            "modifiedTime": "2026-03-01T00:00:00Z",
            "size": "1024",
            "owners": [{"displayName": "Alice", "emailAddress": "alice@example.com"}],
        }

        result = get_file_info(file_id="f1")
        assert result["name"] == "My Document"
        assert result["id"] == "f1"

    @patch("info.get_drive_service")
    def test_includes_shared_drives(self, mock_svc_fn):
        from info import get_file_info

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().get().execute.return_value = {"id": "f1", "name": "F"}

        get_file_info(file_id="f1")
        get_kwargs = mock_svc.files().get.call_args[1]
        assert get_kwargs.get("supportsAllDrives") is True
