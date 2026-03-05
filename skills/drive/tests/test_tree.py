# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "pytest-mock"]
# ///
"""Tests for tree.py — recursive folder tree traversal."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from contracts import ContractViolationError

FOLDER_MIME = "application/vnd.google-apps.folder"


def _make_folder(id: str, name: str) -> dict:
    return {"id": id, "name": name, "mimeType": FOLDER_MIME}


def _make_file(id: str, name: str, mime: str = "text/plain") -> dict:
    return {"id": id, "name": name, "mimeType": mime}


class TestTree:
    @patch("tree.get_drive_service")
    def test_lists_root_folders_at_depth_1(self, mock_svc_fn):
        from tree import list_tree

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {
            "files": [
                _make_folder("f1", "Documents"),
                _make_folder("f2", "Photos"),
                _make_file("x1", "readme.txt"),
            ]
        }

        result = list_tree(depth=1)
        names = [item["name"] for item in result]
        assert "Documents" in names
        assert "Photos" in names
        assert "readme.txt" in names

    @patch("tree.get_drive_service")
    def test_recurses_into_subfolders(self, mock_svc_fn):
        from tree import list_tree

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc

        # First call: root level
        # Second call: inside "Documents" folder
        mock_svc.files().list().execute.side_effect = [
            {"files": [_make_folder("f1", "Documents")]},
            {"files": [_make_file("x1", "report.pdf", "application/pdf")]},
        ]

        result = list_tree(depth=2)
        all_names = [item["name"] for item in result]
        assert "Documents" in all_names
        assert "report.pdf" in all_names

    @patch("tree.get_drive_service")
    def test_respects_depth_limit(self, mock_svc_fn):
        from tree import list_tree

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc

        # Root has a folder, but depth=1 should NOT recurse into it
        mock_svc.files().list().execute.return_value = {
            "files": [_make_folder("f1", "Deep Folder")]
        }

        # Reset call count after mock setup (setup itself calls list() once)
        mock_svc.files().list.reset_mock()

        result = list_tree(depth=1)
        # Should only list root level, not recurse
        assert len(result) == 1
        assert result[0]["name"] == "Deep Folder"
        # files().list() should only have been called once (root level)
        assert mock_svc.files().list.call_count == 1

    @patch("tree.get_drive_service")
    def test_starts_from_specific_folder(self, mock_svc_fn):
        from tree import list_tree

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {"files": []}

        list_tree(folder_id="specific123", depth=1)
        call_kwargs = mock_svc.files().list.call_args[1]
        assert "'specific123' in parents" in call_kwargs["q"]

    @patch("tree.get_drive_service")
    def test_name_filter_includes_matching(self, mock_svc_fn):
        from tree import list_tree

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {
            "files": [
                _make_folder("f1", "Rent Weinbergsweg"),
                _make_folder("f2", "Vacation Photos"),
                _make_file("x1", "weinbergsweg contract.pdf"),
            ]
        }

        result = list_tree(depth=1, name_filter="weinbergsweg")
        names = [item["name"] for item in result]
        assert "Rent Weinbergsweg" in names
        assert "weinbergsweg contract.pdf" in names
        assert "Vacation Photos" not in names

    @patch("tree.get_drive_service")
    def test_name_filter_is_case_insensitive(self, mock_svc_fn):
        from tree import list_tree

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {
            "files": [
                _make_folder("f1", "HEIMSTADEN Docs"),
                _make_file("x1", "heimstaden_invoice.pdf"),
            ]
        }

        result = list_tree(depth=1, name_filter="Heimstaden")
        assert len(result) == 2

    @patch("tree.get_drive_service")
    def test_includes_shared_drives(self, mock_svc_fn):
        from tree import list_tree

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {"files": []}

        list_tree(depth=1)
        call_kwargs = mock_svc.files().list.call_args[1]
        assert call_kwargs["supportsAllDrives"] is True
        assert call_kwargs["includeItemsFromAllDrives"] is True

    @patch("tree.get_drive_service")
    def test_items_have_path_field(self, mock_svc_fn):
        from tree import list_tree

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc

        mock_svc.files().list().execute.side_effect = [
            {"files": [_make_folder("f1", "Rent")]},
            {"files": [_make_file("x1", "contract.pdf")]},
        ]

        result = list_tree(depth=2)
        paths = [item["path"] for item in result]
        assert "Rent" in paths
        assert "Rent/contract.pdf" in paths

    @patch("tree.get_drive_service")
    def test_items_have_depth_field(self, mock_svc_fn):
        from tree import list_tree

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc

        mock_svc.files().list().execute.side_effect = [
            {"files": [_make_folder("f1", "Docs")]},
            {"files": [_make_file("x1", "file.txt")]},
        ]

        result = list_tree(depth=2)
        docs = next(i for i in result if i["name"] == "Docs")
        file = next(i for i in result if i["name"] == "file.txt")
        assert docs["depth"] == 0
        assert file["depth"] == 1

    def test_depth_must_be_positive(self):
        from tree import list_tree

        with pytest.raises(ContractViolationError):
            list_tree(depth=0)

    @patch("tree.get_drive_service")
    def test_name_filter_still_recurses_through_all_folders(self, mock_svc_fn):
        """Name filter should still traverse non-matching folders to find matches deeper."""
        from tree import list_tree

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc

        # Root has "Generic Folder" which contains "Rent Weinbergsweg" file
        mock_svc.files().list().execute.side_effect = [
            {"files": [_make_folder("f1", "Generic Folder")]},
            {"files": [_make_file("x1", "Weinbergsweg lease.pdf")]},
        ]

        result = list_tree(depth=2, name_filter="weinbergsweg")
        names = [item["name"] for item in result]
        # Should find the file inside the non-matching folder
        assert "Weinbergsweg lease.pdf" in names
        # The non-matching folder itself should NOT be in results
        assert "Generic Folder" not in names

    @patch("tree.get_drive_service")
    def test_empty_folder_returns_empty(self, mock_svc_fn):
        from tree import list_tree

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {"files": []}

        result = list_tree(depth=3)
        assert result == []

    @patch("tree.get_drive_service")
    def test_paginates_within_single_folder(self, mock_svc_fn):
        """Should follow nextPageToken within a single folder listing."""
        from tree import list_tree

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc

        page1 = {"files": [_make_file("x1", "file1.txt")], "nextPageToken": "tok"}
        page2 = {"files": [_make_file("x2", "file2.txt")]}
        mock_svc.files().list().execute.side_effect = [page1, page2]

        result = list_tree(depth=1)
        names = [item["name"] for item in result]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert len(result) == 2

    @patch("tree.get_drive_service")
    def test_mime_filter_includes_only_matching_type(self, mock_svc_fn):
        """--mime-type should only return items matching that MIME type (plus folders for structure)."""
        from tree import list_tree

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {
            "files": [
                _make_file("x1", "report.pdf", "application/pdf"),
                _make_file("x2", "notes.txt", "text/plain"),
                _make_file("x3", "photo.jpg", "image/jpeg"),
            ]
        }

        result = list_tree(depth=1, mime_filter="application/pdf")
        names = [item["name"] for item in result]
        assert "report.pdf" in names
        assert "notes.txt" not in names
        assert "photo.jpg" not in names

    @patch("tree.get_drive_service")
    def test_mime_filter_still_traverses_folders(self, mock_svc_fn):
        """Folders should always be traversed even when mime_filter is set, to find matching files inside."""
        from tree import list_tree

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.side_effect = [
            {"files": [_make_folder("f1", "Books")]},
            {"files": [
                _make_file("x1", "Kleppmann.pdf", "application/pdf"),
                _make_file("x2", "notes.txt", "text/plain"),
            ]},
        ]

        result = list_tree(depth=2, mime_filter="application/pdf")
        names = [item["name"] for item in result]
        assert "Kleppmann.pdf" in names
        assert "notes.txt" not in names
        # Folders themselves should NOT appear in mime-filtered results
        assert "Books" not in names

    @patch("tree.get_drive_service")
    def test_mime_filter_combined_with_name_filter(self, mock_svc_fn):
        """Both filters should apply: MIME type AND name substring."""
        from tree import list_tree

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.files().list().execute.return_value = {
            "files": [
                _make_file("x1", "architecture.pdf", "application/pdf"),
                _make_file("x2", "architecture.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                _make_file("x3", "random.pdf", "application/pdf"),
            ]
        }

        result = list_tree(depth=1, name_filter="architecture", mime_filter="application/pdf")
        names = [item["name"] for item in result]
        assert names == ["architecture.pdf"]
