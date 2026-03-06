# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "pytest-mock"]
# ///
"""Tests for comments.py — list and add comments/replies."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from contracts import ContractViolationError


class TestListComments:
    def test_empty_file_id_raises(self):
        from comments import list_comments

        with pytest.raises(ContractViolationError):
            list_comments(file_id="")

    @patch("comments.get_drive_service")
    def test_returns_comments_with_replies(self, mock_svc_fn):
        from comments import list_comments

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.comments().list().execute.return_value = {
            "comments": [
                {
                    "id": "c1",
                    "author": {"displayName": "Alice"},
                    "content": "Good point",
                    "createdTime": "2026-01-15T10:00:00Z",
                    "resolved": False,
                    "replies": [
                        {
                            "author": {"displayName": "Bob"},
                            "content": "Thanks",
                            "createdTime": "2026-01-15T11:00:00Z",
                        }
                    ],
                }
            ]
        }

        result = list_comments(file_id="doc1")
        assert len(result) == 1
        assert result[0]["author"]["displayName"] == "Alice"
        assert len(result[0]["replies"]) == 1


class TestAddComment:
    def test_empty_file_id_raises(self):
        from comments import add_comment

        with pytest.raises(ContractViolationError):
            add_comment(file_id="", content="test")

    def test_empty_content_raises(self):
        from comments import add_comment

        with pytest.raises(ContractViolationError):
            add_comment(file_id="f1", content="")

    @patch("comments.get_drive_service")
    def test_creates_comment(self, mock_svc_fn):
        from comments import add_comment

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.comments().create().execute.return_value = {
            "id": "c_new", "content": "New comment"
        }

        result = add_comment(file_id="doc1", content="New comment")
        assert result["id"] == "c_new"


class TestAddReply:
    def test_empty_comment_id_raises(self):
        from comments import add_reply

        with pytest.raises(ContractViolationError):
            add_reply(file_id="f1", comment_id="", content="reply")

    @patch("comments.get_drive_service")
    def test_creates_reply(self, mock_svc_fn):
        from comments import add_reply

        mock_svc = MagicMock()
        mock_svc_fn.return_value = mock_svc
        mock_svc.replies().create().execute.return_value = {
            "id": "r_new", "content": "My reply"
        }

        result = add_reply(file_id="doc1", comment_id="c1", content="My reply")
        assert result["id"] == "r_new"
