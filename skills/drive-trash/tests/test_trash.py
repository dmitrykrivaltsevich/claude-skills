# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "pytest-mock"]
# ///
"""Tests for trash.py — trash and restore files."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from contracts import ContractViolationError


class TestTrash:
    def test_empty_file_id_raises(self):
        from trash import trash_file

        with pytest.raises(ContractViolationError):
            trash_file(file_id="")

    @patch("trash.get_drive_service")
    def test_trashes_file(self, mock_svc_fn):
        from trash import trash_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().get().execute.return_value = {
            "id": "f1", "name": "report.docx", "mimeType": "application/pdf", "trashed": False
        }
        mock_svc.files().update().execute.return_value = {
            "id": "f1", "name": "report.docx", "mimeType": "application/pdf", "trashed": True
        }

        result = trash_file(file_id="f1")
        assert result["trashed"] is True

    @patch("trash.get_drive_service")
    def test_skips_already_trashed(self, mock_svc_fn):
        from trash import trash_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().get().execute.return_value = {
            "id": "f1", "name": "old.txt", "mimeType": "text/plain", "trashed": True
        }

        result = trash_file(file_id="f1")
        # Should return immediately without calling update
        assert result["trashed"] is True

    @patch("trash.get_drive_service")
    def test_includes_shared_drives(self, mock_svc_fn):
        from trash import trash_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().get().execute.return_value = {
            "id": "f1", "name": "f", "trashed": False, "mimeType": "x"
        }
        mock_svc.files().update().execute.return_value = {
            "id": "f1", "name": "f", "trashed": True, "mimeType": "x"
        }

        trash_file(file_id="f1")
        update_kwargs = mock_svc.files().update.call_args[1]
        assert update_kwargs.get("supportsAllDrives") is True


class TestRestore:
    def test_empty_file_id_raises(self):
        from trash import restore_file

        with pytest.raises(ContractViolationError):
            restore_file(file_id="")

    @patch("trash.get_drive_service")
    def test_restores_file(self, mock_svc_fn):
        from trash import restore_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().update().execute.return_value = {
            "id": "f1", "name": "report.docx", "mimeType": "application/pdf", "trashed": False
        }

        result = restore_file(file_id="f1")
        assert result["trashed"] is False
