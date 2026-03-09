"""Tests for DuckDuckGo search functionality."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from contracts import ContractViolationError
from search import search_image, search_news, search_text


class TestSearchTextPreconditions:
    """Test query validation via @precondition."""

    def test_empty_query_raises(self):
        with pytest.raises(ContractViolationError, match="at least 2 characters"):
            search_text("")

    def test_single_char_raises(self):
        with pytest.raises(ContractViolationError, match="at least 2 characters"):
            search_text("a")

    def test_whitespace_only_raises(self):
        with pytest.raises(ContractViolationError, match="at least 2 characters"):
            search_text("   ")


class TestSearchText:
    """Test text search result processing."""

    @patch("search.DDGS")
    def test_returns_formatted_results(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.text.return_value = [
            {"title": "Python Docs", "href": "https://docs.python.org", "body": "Official documentation"},
            {"title": "Real Python", "href": "https://realpython.com", "body": "Tutorials and guides"},
        ]

        results = search_text("python tutorial")

        assert len(results) == 2
        assert results[0]["title"] == "Python Docs"
        assert results[0]["url"] == "https://docs.python.org"
        assert results[0]["description"] == "Official documentation"

    @patch("search.DDGS")
    def test_truncates_long_descriptions(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.text.return_value = [
            {"title": "Long", "href": "https://example.com", "body": "x" * 1000},
        ]

        results = search_text("test query")

        assert len(results[0]["description"]) <= 500

    @patch("search.DDGS")
    def test_handles_empty_results(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.text.return_value = []

        results = search_text("obscure query xyz")

        assert results == []


class TestSearchImage:
    """Test image search result processing."""

    def test_short_query_raises(self):
        with pytest.raises(ContractViolationError):
            search_image("x")

    @patch("search.DDGS")
    def test_returns_image_results(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.images.return_value = [
            {
                "title": "Cat photo",
                "image": "https://example.com/cat.jpg",
                "thumbnail": "https://example.com/cat_thumb.jpg",
                "url": "https://example.com/cats",
                "source": "Example",
            },
        ]

        results = search_image("cats")

        assert len(results) == 1
        assert results[0]["title"] == "Cat photo"
        assert results[0]["image"] == "https://example.com/cat.jpg"

    @patch("search.DDGS")
    def test_passes_filter_params(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.images.return_value = []

        search_image("dogs", size="Large", type_="photo", color="Brown")

        mock_ddgs.images.assert_called_once_with(
            "dogs", max_results=30, size="Large", type_image="photo", color="Brown"
        )

    @patch("search.DDGS")
    def test_omits_none_filters(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.images.return_value = []

        search_image("cats")

        mock_ddgs.images.assert_called_once_with("cats", max_results=30)


class TestSearchNews:
    """Test news search result processing."""

    def test_empty_query_raises(self):
        with pytest.raises(ContractViolationError):
            search_news("")

    @patch("search.DDGS")
    def test_returns_news_results(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.return_value = [
            {
                "title": "Tech News",
                "url": "https://example.com/news",
                "body": "Latest tech developments",
                "date": "2026-03-09",
                "source": "TechCrunch",
            },
        ]

        results = search_news("technology")

        assert len(results) == 1
        assert results[0]["title"] == "Tech News"
        assert results[0]["date"] == "2026-03-09"
        assert results[0]["source"] == "TechCrunch"

    @patch("search.DDGS")
    def test_truncates_long_news_descriptions(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.return_value = [
            {
                "title": "Long News",
                "url": "https://example.com",
                "body": "y" * 1000,
                "date": "2026-03-09",
                "source": "Source",
            },
        ]

        results = search_news("long news")

        assert len(results[0]["description"]) <= 500
