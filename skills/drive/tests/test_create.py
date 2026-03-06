# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest",
#     "pytest-mock",
#     "keyring",
#     "google-api-python-client",
#     "google-auth",
#     "google-auth-httplib2",
# ]
# ///
"""Tests for create.py — create Google Drive items."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from contracts import ContractViolationError


class TestCreate:
    def test_empty_name_raises(self):
        from create import create_item

        with pytest.raises(ContractViolationError):
            create_item(name="", item_type="doc")

    def test_invalid_type_raises(self):
        from create import create_item

        with pytest.raises(ContractViolationError):
            create_item(name="Test", item_type="invalid")

    @patch("create.get_drive_service")
    def test_creates_google_doc(self, mock_svc_fn):
        from create import create_item

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().create().execute.return_value = {
            "id": "new1", "name": "My Doc", "mimeType": "application/vnd.google-apps.document"
        }

        result = create_item(name="My Doc", item_type="doc")
        assert result["id"] == "new1"

    @patch("create.get_drive_service")
    def test_creates_folder(self, mock_svc_fn):
        from create import create_item

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().create().execute.return_value = {
            "id": "folder1", "name": "New Folder", "mimeType": "application/vnd.google-apps.folder"
        }

        result = create_item(name="New Folder", item_type="folder")
        create_kwargs = mock_svc.files().create.call_args[1]
        assert create_kwargs["body"]["mimeType"] == "application/vnd.google-apps.folder"

    @patch("create.get_drive_service")
    def test_creates_in_specific_folder(self, mock_svc_fn):
        from create import create_item

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().create().execute.return_value = {"id": "x", "name": "y", "mimeType": "z"}

        create_item(name="Test", item_type="sheet", folder_id="parent123")
        create_kwargs = mock_svc.files().create.call_args[1]
        assert "parent123" in create_kwargs["body"].get("parents", [])

    @patch("create.get_drive_service")
    def test_includes_shared_drives(self, mock_svc_fn):
        from create import create_item

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().create().execute.return_value = {"id": "x", "name": "y", "mimeType": "z"}

        create_item(name="Test", item_type="doc")
        create_kwargs = mock_svc.files().create.call_args[1]
        assert create_kwargs.get("supportsAllDrives") is True
