"""Tests for top_news.py — multi-source news fetcher."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from top_news import (
    QUERY_GROUPS,
    _build_query_map,
    _chop_dateline,
    extract_byline,
    fetch_news,
)


class TestChopDateline:
    """Test dateline suffix removal from name tokens."""

    def test_plain_name_unchanged(self):
        assert _chop_dateline("Smith") == "Smith"

    def test_allcaps_suffix_removed(self):
        assert _chop_dateline("QueenNEW") == "Queen"

    def test_month_suffix_removed(self):
        assert _chop_dateline("WolfeMarch") == "Wolfe"

    def test_mc_prefix_preserved(self):
        assert _chop_dateline("McCoy") == "McCoy"

    def test_mac_prefix_preserved(self):
        assert _chop_dateline("MacDonald") == "MacDonald"

    def test_lowercase_suffix_kept(self):
        """Mixed case like 'Smithson' should not be chopped."""
        assert _chop_dateline("Smithson") == "Smithson"

    def test_allcaps_city_chopped(self):
        assert _chop_dateline("JohnsonWASHINGTON") == "Johnson"

    def test_multiple_month_names(self):
        assert _chop_dateline("BrownJanuary") == "Brown"
        assert _chop_dateline("DavisFebruary") == "Davis"
        assert _chop_dateline("WilsonNovember") == "Wilson"


class TestExtractByline:
    """Test byline extraction from article bodies."""

    def test_simple_byline(self):
        assert extract_byline("By Jane Smith\nLorem ipsum") == "Jane Smith"

    def test_two_authors(self):
        result = extract_byline("By Jane Smith and John Doe\nLorem ipsum")
        assert result == "Jane Smith and John Doe"

    def test_byline_with_comma(self):
        assert extract_byline("By Jane Smith,\nReporters") == "Jane Smith"

    def test_byline_with_dateline_on_newline(self):
        """'By Jack Queen\\nNEW YORK' should NOT bleed city into name."""
        result = extract_byline("By Jack Queen\nNEW YORK, March 9 (Reuters)")
        assert result == "Jack Queen"

    def test_no_byline(self):
        assert extract_byline("Lorem ipsum dolor sit amet") == ""

    def test_empty_body(self):
        assert extract_byline("") == ""

    def test_byline_with_hyphenated_name(self):
        assert extract_byline("By Mary-Jane Watson\nStory text") == "Mary-Jane Watson"

    def test_byline_with_accented_name(self):
        result = extract_byline("By José García\nStory about")
        assert result == "José García"

    def test_regex_captures_at_most_five_words(self):
        """The regex {1,4} pattern captures at most 5 name words, silently
        ignoring trailing words.  This is intentionally conservative."""
        result = extract_byline(
            "By One Two Three Four Five Six Seven Eight\nBody"
        )
        assert result == "One Two Three Four Five"

    def test_byline_only_in_first_300_chars(self):
        """Byline search is limited to first 300 chars."""
        body = "x" * 300 + "\nBy Hidden Author\nStory"
        assert extract_byline(body) == ""

    def test_three_word_name(self):
        result = extract_byline("By Mary Jane Watson\nThe story")
        assert result == "Mary Jane Watson"


class TestBuildQueryMap:
    """Test query map construction from group names."""

    def test_single_group(self):
        qmap = _build_query_map(["wires"])
        assert "site:reuters.com" in qmap
        assert qmap["site:reuters.com"] == "wires"
        assert "site:apnews.com" in qmap

    def test_multiple_groups(self):
        qmap = _build_query_map(["wires", "tech"])
        assert "site:reuters.com" in qmap
        assert "site:techcrunch.com" in qmap
        assert qmap["site:techcrunch.com"] == "tech"

    def test_unknown_group_returns_empty(self):
        qmap = _build_query_map(["nonexistent"])
        assert len(qmap) == 0

    def test_all_groups(self):
        qmap = _build_query_map(list(QUERY_GROUPS))
        # Should have at least 60 queries across all groups
        assert len(qmap) >= 60


class TestFetchNews:
    """Test news fetching with mocked DDG API."""

    @patch("top_news.DDGS")
    def test_returns_structured_results(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.return_value = [
            {
                "title": "Test Story",
                "url": "https://example.com/story",
                "source": "Example News",
                "date": "2026-03-11",
                "body": "By Author Name\nStory body here",
            }
        ]

        results = fetch_news({"test query": "broad"}, per_query=5)

        assert len(results) == 1
        assert results[0]["title"] == "Test Story"
        assert results[0]["query_group"] == "broad"
        assert results[0]["url"] == "https://example.com/story"

    @patch("top_news.DDGS")
    def test_deduplicates_by_url(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.return_value = [
            {
                "title": "Duplicate Story",
                "url": "https://example.com/same-story",
                "source": "News",
                "date": "2026-03-11",
                "body": "Body text",
            }
        ]

        results = fetch_news(
            {"query1": "broad", "query2": "wires"}, per_query=5
        )

        urls = [r["url"] for r in results]
        assert urls.count("https://example.com/same-story") == 1

    @patch("top_news.DDGS")
    def test_extracts_byline_from_body(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.return_value = [
            {
                "title": "Story",
                "url": "https://example.com/authored",
                "source": "News",
                "date": "2026-03-11",
                "body": "By Sarah Johnson\nThe article text...",
                "author": "",
            }
        ]

        results = fetch_news({"query": "broad"}, per_query=5)

        assert results[0]["author"] == "Sarah Johnson"

    @patch("top_news.DDGS")
    def test_truncates_long_descriptions(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.return_value = [
            {
                "title": "Long",
                "url": "https://example.com/long",
                "source": "News",
                "date": "2026-03-11",
                "body": "x" * 5000,
            }
        ]

        results = fetch_news({"query": "broad"}, per_query=5)

        assert len(results[0]["description"]) <= 1200

    @patch("top_news.DDGS")
    def test_handles_api_errors_gracefully(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.side_effect = Exception("Rate limited")

        results = fetch_news({"query": "broad"}, per_query=5)

        assert results == []
