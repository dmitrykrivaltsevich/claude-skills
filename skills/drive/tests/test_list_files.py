# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "pytest-mock"]
# ///
"""Tests for list_files.py — list folder contents."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestListFiles:
    @patch("list_files.get_drive_service")
    def test_lists_root_by_default(self, mock_svc_fn):
        from list_files import list_folder

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {
            "files": [{"id": "1", "name": "My Doc", "mimeType": "application/vnd.google-apps.document"}]
        }

        results = list_folder()
        assert len(results) == 1
        assert results[0]["name"] == "My Doc"

    @patch("list_files.get_drive_service")
    def test_lists_specific_folder(self, mock_svc_fn):
        from list_files import list_folder

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {"files": []}

        list_folder(folder_id="folder456")
        call_kwargs = mock_svc.files().list.call_args[1]
        assert "'folder456' in parents" in call_kwargs["q"]

    @patch("list_files.get_drive_service")
    def test_respects_page_size(self, mock_svc_fn):
        from list_files import list_folder

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {"files": []}

        list_folder(page_size=50)
        call_kwargs = mock_svc.files().list.call_args[1]
        assert call_kwargs["pageSize"] == 50

    @patch("list_files.get_drive_service")
    def test_includes_shared_drives(self, mock_svc_fn):
        from list_files import list_folder

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {"files": []}

        list_folder()
        call_kwargs = mock_svc.files().list.call_args[1]
        assert call_kwargs["supportsAllDrives"] is True
        assert call_kwargs["includeItemsFromAllDrives"] is True

    @patch("list_files.get_drive_service")
    def test_order_by(self, mock_svc_fn):
        from list_files import list_folder

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {"files": []}

        list_folder(order_by="modifiedTime desc")
        call_kwargs = mock_svc.files().list.call_args[1]
        assert call_kwargs["orderBy"] == "modifiedTime desc"

    @patch("list_files.get_drive_service")
    def test_paginates_through_all_results(self, mock_svc_fn):
        """Should follow nextPageToken to collect all pages of results."""
        from list_files import list_folder

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc

        page1 = {"files": [{"id": "1", "name": "file1"}], "nextPageToken": "tok"}
        page2 = {"files": [{"id": "2", "name": "file2"}]}
        mock_svc.files().list().execute.side_effect = [page1, page2]

        results = list_folder()
        assert len(results) == 2
        assert results[0]["id"] == "1"
        assert results[1]["id"] == "2"
