# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "pytest-mock"]
# ///
"""Tests for upload.py — upload files to Google Drive."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from contracts import ContractViolationError


class TestUpload:
    def test_empty_file_path_raises(self):
        from upload import upload_file

        with pytest.raises(ContractViolationError):
            upload_file(file_path="")

    @patch("upload.get_drive_service")
    @patch("upload.MediaFileUpload")
    @patch("os.path.exists", return_value=True)
    @patch("os.path.basename", return_value="report.pdf")
    def test_uploads_file(self, mock_bn, mock_exists, mock_media_cls, mock_svc_fn):
        from upload import upload_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().create().execute.return_value = {
            "id": "new123", "name": "report.pdf"
        }

        result = upload_file(file_path="/path/to/report.pdf")
        assert result["id"] == "new123"

    @patch("upload.get_drive_service")
    @patch("upload.MediaFileUpload")
    @patch("os.path.exists", return_value=True)
    @patch("os.path.basename", return_value="report.pdf")
    def test_uploads_to_specific_folder(self, mock_bn, mock_exists, mock_media_cls, mock_svc_fn):
        from upload import upload_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().create().execute.return_value = {
            "id": "new123", "name": "report.pdf"
        }

        upload_file(file_path="/path/to/report.pdf", folder_id="folder789")
        create_kwargs = mock_svc.files().create.call_args[1]
        body = create_kwargs["body"]
        assert "folder789" in body.get("parents", [])

    @patch("upload.get_drive_service")
    @patch("upload.MediaFileUpload")
    @patch("os.path.exists", return_value=True)
    @patch("os.path.basename", return_value="report.pdf")
    def test_includes_shared_drives(self, mock_bn, mock_exists, mock_media_cls, mock_svc_fn):
        from upload import upload_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().create().execute.return_value = {"id": "x", "name": "y"}

        upload_file(file_path="/path/to/report.pdf")
        create_kwargs = mock_svc.files().create.call_args[1]
        assert create_kwargs.get("supportsAllDrives") is True
