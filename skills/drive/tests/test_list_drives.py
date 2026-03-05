# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "pytest-mock"]
# ///
"""Tests for list_drives.py — list available Shared Drives."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestListDrives:
    @patch("list_drives.get_drive_service")
    def test_returns_shared_drives(self, mock_svc_fn):
        from list_drives import list_shared_drives

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.drives().list().execute.return_value = {
            "drives": [
                {"id": "d1", "name": "Engineering"},
                {"id": "d2", "name": "Marketing"},
            ]
        }

        results = list_shared_drives()
        assert len(results) == 2
        assert results[0]["name"] == "Engineering"
        assert results[1]["id"] == "d2"

    @patch("list_drives.get_drive_service")
    def test_returns_empty_list_when_no_drives(self, mock_svc_fn):
        from list_drives import list_shared_drives

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.drives().list().execute.return_value = {"drives": []}

        results = list_shared_drives()
        assert results == []

    @patch("list_drives.get_drive_service")
    def test_returns_empty_when_key_missing(self, mock_svc_fn):
        from list_drives import list_shared_drives

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.drives().list().execute.return_value = {}

        results = list_shared_drives()
        assert results == []

    @patch("list_drives.get_drive_service")
    def test_paginates_through_all_results(self, mock_svc_fn):
        from list_drives import list_shared_drives

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc

        page1 = {"drives": [{"id": "d1", "name": "A"}], "nextPageToken": "tok2"}
        page2 = {"drives": [{"id": "d2", "name": "B"}]}
        mock_svc.drives().list().execute.side_effect = [page1, page2]

        results = list_shared_drives()
        assert len(results) == 2
        assert results[0]["name"] == "A"
        assert results[1]["name"] == "B"

    @patch("list_drives.get_drive_service")
    def test_respects_page_size(self, mock_svc_fn):
        from list_drives import list_shared_drives

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.drives().list().execute.return_value = {"drives": []}

        list_shared_drives(page_size=50)
        call_kwargs = mock_svc.drives().list.call_args[1]
        assert call_kwargs["pageSize"] == 50
