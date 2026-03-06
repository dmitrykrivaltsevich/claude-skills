# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "pytest-mock"]
# ///
"""Tests for download.py — download/export files with inline comments."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock, mock_open

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from contracts import ContractViolationError


class TestDownload:
    def test_empty_file_id_raises(self):
        from download import download_file

        with pytest.raises(ContractViolationError):
            download_file(file_id="", fmt="md")

    @patch("download.get_drive_service")
    def test_exports_google_doc_as_markdown(self, mock_svc_fn):
        from download import download_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc

        # File metadata
        mock_svc.files().get().execute.return_value = {
            "id": "doc1",
            "name": "My Doc",
            "mimeType": "application/vnd.google-apps.document",
        }

        # Export content
        mock_svc.files().export_media.return_value.execute.return_value = b"# Hello\n\nWorld"

        # No comments
        mock_svc.comments().list().execute.return_value = {"comments": []}

        result = download_file(file_id="doc1", fmt="md", output_dir="/tmp")
        assert result["name"] == "My Doc"
        assert result["format"] == "md"

    @patch("download.get_drive_service")
    def test_downloads_regular_file(self, mock_svc_fn):
        from download import download_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc

        mock_svc.files().get().execute.return_value = {
            "id": "file1",
            "name": "photo.jpg",
            "mimeType": "image/jpeg",
        }

        mock_svc.files().get_media.return_value.execute.return_value = b"\xff\xd8\xff"

        mock_svc.comments().list().execute.return_value = {"comments": []}

        result = download_file(file_id="file1", output_dir="/tmp")
        assert result["name"] == "photo.jpg"

    @patch("download.get_drive_service")
    def test_includes_shared_drives_in_metadata_call(self, mock_svc_fn):
        from download import download_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().get().execute.return_value = {
            "id": "f1", "name": "f", "mimeType": "text/plain"
        }
        mock_svc.files().get_media.return_value.execute.return_value = b"data"
        mock_svc.comments().list().execute.return_value = {"comments": []}

        download_file(file_id="f1", output_dir="/tmp")
        get_call_kwargs = mock_svc.files().get.call_args[1]
        assert get_call_kwargs.get("supportsAllDrives") is True


class TestInlineComments:
    @patch("download.get_drive_service")
    def test_markdown_export_includes_comments_section(self, mock_svc_fn):
        from download import download_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc

        mock_svc.files().get().execute.return_value = {
            "id": "doc1", "name": "Doc", "mimeType": "application/vnd.google-apps.document"
        }
        mock_svc.files().export_media.return_value.execute.return_value = b"# Content"
        mock_svc.comments().list().execute.return_value = {
            "comments": [
                {
                    "id": "c1",
                    "author": {"displayName": "Alice"},
                    "content": "Great point!",
                    "createdTime": "2026-01-15T10:00:00Z",
                    "resolved": False,
                    "quotedFileContent": {"value": "some text"},
                    "replies": [
                        {
                            "author": {"displayName": "Bob"},
                            "content": "Thanks!",
                            "createdTime": "2026-01-15T11:00:00Z",
                        }
                    ],
                }
            ]
        }

        result = download_file(file_id="doc1", fmt="md", output_dir="/tmp")
        assert result.get("comments_count", 0) == 1

    @patch("download.get_drive_service")
    def test_binary_export_prints_comments_to_stdout(self, mock_svc_fn, capsys):
        from download import download_file

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc

        mock_svc.files().get().execute.return_value = {
            "id": "doc1", "name": "Doc", "mimeType": "application/vnd.google-apps.document"
        }
        mock_svc.files().export_media.return_value.execute.return_value = b"%PDF-data"
        mock_svc.comments().list().execute.return_value = {
            "comments": [
                {
                    "id": "c1",
                    "author": {"displayName": "Alice"},
                    "content": "Fix typo",
                    "createdTime": "2026-01-15T10:00:00Z",
                    "resolved": True,
                    "quotedFileContent": {"value": "teh"},
                    "replies": [],
                }
            ]
        }

        result = download_file(file_id="doc1", fmt="pdf", output_dir="/tmp")
        captured = capsys.readouterr()
        assert "Alice" in captured.out
        assert "Fix typo" in captured.out
