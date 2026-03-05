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

    @patch("search.get_drive_service")
    def test_default_search_includes_name_and_fulltext(self, mock_svc_fn):
        """Default search should match both file content and file/folder names."""
        from search import search_files

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {"files": []}

        search_files(query="Weinbergsweg")
        call_kwargs = mock_svc.files().list.call_args[1]
        q = call_kwargs["q"]
        assert "fullText contains" in q
        assert "name contains" in q

    @patch("search.get_drive_service")
    def test_name_only_flag_excludes_fulltext(self, mock_svc_fn):
        """With name_only=True, should only search by name, not fullText."""
        from search import search_files

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {"files": []}

        search_files(query="rent", name_only=True)
        call_kwargs = mock_svc.files().list.call_args[1]
        q = call_kwargs["q"]
        assert "name contains" in q
        assert "fullText contains" not in q

    @patch("search.get_drive_service")
    def test_paginates_through_all_results(self, mock_svc_fn):
        """Should follow nextPageToken to collect all pages of results."""
        from search import search_files

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc

        page1 = {"files": [{"id": "1", "name": "file1"}], "nextPageToken": "token2"}
        page2 = {"files": [{"id": "2", "name": "file2"}]}
        mock_svc.files().list().execute.side_effect = [page1, page2]

        results = search_files(query="test")
        assert len(results) == 2
        assert results[0]["id"] == "1"
        assert results[1]["id"] == "2"

    @patch("search.get_drive_service")
    def test_query_with_single_quote_is_escaped(self, mock_svc_fn):
        """A query containing apostrophe should not break the API query string."""
        from search import search_files

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {"files": []}

        search_files(query="O'Brien")
        call_kwargs = mock_svc.files().list.call_args[1]
        q = call_kwargs["q"]
        # The apostrophe must be escaped so the query string is valid
        assert "O\\'Brien" in q
        assert "O'Brien" not in q


class TestQueryDrive:
    """Tests for query_drive() — raw Drive API query passthrough."""

    @patch("search.get_drive_service")
    def test_passes_raw_query_directly(self, mock_svc_fn):
        from search import query_drive

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {"files": []}

        raw = "modifiedTime > '2025-01-01' and name contains 'rent' and mimeType = 'application/pdf'"
        query_drive(q=raw)
        call_kwargs = mock_svc.files().list.call_args[1]
        assert call_kwargs["q"] == raw

    @patch("search.get_drive_service")
    def test_no_wrapping_or_escaping(self, mock_svc_fn):
        """Raw query must not be modified — LLM constructs it."""
        from search import query_drive

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {"files": []}

        raw = "sharedWithMe = true and fullText contains 'budget'"
        query_drive(q=raw)
        call_kwargs = mock_svc.files().list.call_args[1]
        assert call_kwargs["q"] == raw

    @patch("search.get_drive_service")
    def test_paginates(self, mock_svc_fn):
        from search import query_drive

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc

        page1 = {"files": [{"id": "1"}], "nextPageToken": "tok"}
        page2 = {"files": [{"id": "2"}]}
        mock_svc.files().list().execute.side_effect = [page1, page2]

        results = query_drive(q="trashed = false")
        assert len(results) == 2

    @patch("search.get_drive_service")
    def test_includes_shared_drives(self, mock_svc_fn):
        from search import query_drive

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {"files": []}

        query_drive(q="trashed = false")
        call_kwargs = mock_svc.files().list.call_args[1]
        assert call_kwargs["supportsAllDrives"] is True
        assert call_kwargs["includeItemsFromAllDrives"] is True

    def test_empty_q_raises(self):
        from search import query_drive

        with pytest.raises(ContractViolationError):
            query_drive(q="")
