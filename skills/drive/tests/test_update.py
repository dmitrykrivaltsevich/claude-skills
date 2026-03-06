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
"""Tests for update.py — update file metadata, rename, move."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from contracts import ContractViolationError


class TestUpdate:
    def test_empty_file_id_raises(self):
        from update import update_file

        with pytest.raises(ContractViolationError):
            update_file(file_id="")

    @patch("update.get_drive_service")
    def test_renames_file(self, mock_svc_fn):
        from update import update_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().update().execute.return_value = {
            "id": "f1", "name": "New Name"
        }

        result = update_file(file_id="f1", name="New Name")
        assert result["name"] == "New Name"

    @patch("update.get_drive_service")
    def test_moves_file(self, mock_svc_fn):
        from update import update_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc

        mock_svc.files().get().execute.return_value = {"parents": ["old_parent"]}
        mock_svc.files().update().execute.return_value = {"id": "f1", "name": "F"}

        result = update_file(file_id="f1", move_to="new_parent")
        update_kwargs = mock_svc.files().update.call_args[1]
        assert update_kwargs.get("addParents") == "new_parent"
        assert update_kwargs.get("removeParents") == "old_parent"

    @patch("update.get_drive_service")
    def test_stars_file(self, mock_svc_fn):
        from update import update_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().update().execute.return_value = {"id": "f1", "name": "F"}

        update_file(file_id="f1", star=True)
        update_kwargs = mock_svc.files().update.call_args[1]
        assert update_kwargs["body"].get("starred") is True

    @patch("update.get_drive_service")
    def test_includes_shared_drives(self, mock_svc_fn):
        from update import update_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().update().execute.return_value = {"id": "f1", "name": "F"}

        update_file(file_id="f1", name="X")
        update_kwargs = mock_svc.files().update.call_args[1]
        assert update_kwargs.get("supportsAllDrives") is True
