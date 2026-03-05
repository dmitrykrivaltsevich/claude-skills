# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "pytest-mock"]
# ///
"""Tests for search.py — Google Drive search."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from contracts import ContractViolationError


class TestSearch:
    @patch("search.get_drive_service")
    def test_search_by_query(self, mock_svc_fn):
        from search import search_files

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {
            "files": [
                {"id": "abc", "name": "Report.docx", "mimeType": "application/vnd.google-apps.document"}
            ]
        }

        results = search_files(query="Report")
        assert len(results) == 1
        assert results[0]["name"] == "Report.docx"

    @patch("search.get_drive_service")
    def test_search_includes_shared_drives(self, mock_svc_fn):
        from search import search_files

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {"files": []}

        search_files(query="test")
        call_kwargs = mock_svc.files().list.call_args[1]
        assert call_kwargs.get("supportsAllDrives") is True
        assert call_kwargs.get("includeItemsFromAllDrives") is True

    @patch("search.get_drive_service")
    def test_search_with_mime_type_filter(self, mock_svc_fn):
        from search import search_files

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {"files": []}

        search_files(query="budget", mime_type="application/vnd.google-apps.spreadsheet")
        call_kwargs = mock_svc.files().list.call_args[1]
        assert "mimeType" in call_kwargs["q"]

    @patch("search.get_drive_service")
    def test_search_with_folder_id(self, mock_svc_fn):
        from search import search_files

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {"files": []}

        search_files(query="notes", folder_id="folder123")
        call_kwargs = mock_svc.files().list.call_args[1]
        assert "folder123" in call_kwargs["q"]

    def test_empty_query_raises(self):
        from search import search_files

        with pytest.raises(ContractViolationError):
            search_files(query="")

    @patch("search.get_drive_service")
    def test_returns_standard_fields(self, mock_svc_fn):
        from search import search_files

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {
            "files": [{"id": "1", "name": "f", "mimeType": "text/plain", "modifiedTime": "2026-01-01"}]
        }

        results = search_files(query="f")
        assert "id" in results[0]
        assert "name" in results[0]
