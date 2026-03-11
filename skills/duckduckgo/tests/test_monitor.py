"""Tests for monitor.py — persistent topic watch."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from contracts import ContractViolationError
from monitor import _normalize_url, monitor_topic


class TestNormalizeUrl:
    """Test URL normalization for deduplication."""

    def test_strips_https(self):
        assert _normalize_url("https://example.com/page") == "example.com/page"

    def test_strips_http(self):
        assert _normalize_url("http://example.com/page") == "example.com/page"

    def test_strips_www(self):
        assert _normalize_url("https://www.example.com/page") == "example.com/page"

    def test_strips_trailing_slash(self):
        assert _normalize_url("https://example.com/page/") == "example.com/page"

    def test_strips_protocol_and_www_and_slash(self):
        assert _normalize_url("https://www.example.com/path/") == "example.com/path"


class TestMonitorTopicPreconditions:
    """Test topic validation via @precondition."""

    def test_short_topic_raises(self):
        with pytest.raises(ContractViolationError, match="at least 2"):
            monitor_topic("x")

    def test_whitespace_only_raises(self):
        with pytest.raises(ContractViolationError, match="at least 2"):
            monitor_topic(" ")


class TestMonitorTopic:
    """Test topic monitoring logic."""

    @patch("monitor.DDGS")
    def test_first_run_all_results_new(self, mock_ddgs_cls, tmp_path):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.return_value = [
            {
                "title": "Story 1",
                "url": "https://example.com/1",
                "body": "First story",
                "date": "2026-03-11",
                "source": "Ex",
            },
            {
                "title": "Story 2",
                "url": "https://example.com/2",
                "body": "Second story",
                "date": "2026-03-11",
                "source": "Ex",
            },
        ]

        state = tmp_path / "state.json"
        result = monitor_topic("test topic", state_file=state)

        assert result["new_count"] == 2
        assert len(result["new_results"]) == 2
        assert state.exists()

    @patch("monitor.DDGS")
    def test_second_run_filters_seen(self, mock_ddgs_cls, tmp_path):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs

        # Pre-populate state file with one seen URL
        state = tmp_path / "state.json"
        state.write_text(json.dumps([
            {"url": "https://example.com/old", "title": "Old Story"},
        ]))

        mock_ddgs.news.return_value = [
            {
                "title": "Old Story",
                "url": "https://example.com/old",
                "body": "Already seen",
                "date": "",
                "source": "",
            },
            {
                "title": "New Story",
                "url": "https://example.com/new",
                "body": "Brand new",
                "date": "",
                "source": "",
            },
        ]

        result = monitor_topic("test topic", state_file=state)

        assert result["new_count"] == 1
        assert result["new_results"][0]["title"] == "New Story"

    @patch("monitor.DDGS")
    def test_state_file_updated_with_new(self, mock_ddgs_cls, tmp_path):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.return_value = [
            {
                "title": "New",
                "url": "https://example.com/new",
                "body": "Content",
                "date": "",
                "source": "",
            },
        ]

        state = tmp_path / "state.json"
        monitor_topic("test topic", state_file=state)

        saved = json.loads(state.read_text())
        assert len(saved) == 1
        assert saved[0]["url"] == "https://example.com/new"

    @patch("monitor.DDGS")
    def test_state_file_appends_not_overwrites(self, mock_ddgs_cls, tmp_path):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs

        state = tmp_path / "state.json"
        state.write_text(json.dumps([
            {"url": "https://example.com/old", "title": "Old"},
        ]))

        mock_ddgs.news.return_value = [
            {
                "title": "New",
                "url": "https://example.com/new",
                "body": "Content",
                "date": "",
                "source": "",
            },
        ]

        monitor_topic("test topic", state_file=state)

        saved = json.loads(state.read_text())
        assert len(saved) == 2  # old + new

    @patch("monitor.DDGS")
    def test_no_new_results_doesnt_modify_state(self, mock_ddgs_cls, tmp_path):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs

        state = tmp_path / "state.json"
        original = [{"url": "https://example.com/only", "title": "Only"}]
        state.write_text(json.dumps(original))

        mock_ddgs.news.return_value = [
            {
                "title": "Only",
                "url": "https://example.com/only",
                "body": "",
                "date": "",
                "source": "",
            },
        ]

        result = monitor_topic("test topic", state_file=state)

        assert result["new_count"] == 0
        # State file should not be rewritten
        saved = json.loads(state.read_text())
        assert len(saved) == 1

    @patch("monitor.DDGS")
    def test_returns_state_file_path(self, mock_ddgs_cls, tmp_path):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.return_value = []

        state = tmp_path / "state.json"
        result = monitor_topic("test topic", state_file=state)

        assert result["state_file"] == str(state)

    @patch("monitor.DDGS")
    def test_text_search_type(self, mock_ddgs_cls, tmp_path):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.text.return_value = [
            {
                "title": "Text Result",
                "href": "https://example.com/text",
                "body": "Content",
            },
        ]

        state = tmp_path / "state.json"
        result = monitor_topic("test topic", state_file=state, search_type="text")

        assert result["new_count"] == 1
        mock_ddgs.text.assert_called_once()
