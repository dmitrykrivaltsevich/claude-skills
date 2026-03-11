"""Tests for translate_search.py — multi-region parallel search."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from contracts import ContractViolationError
from translate_search import _parse_query, _search_region, multi_region_search


class TestParseQuery:
    """Test region:query parsing."""

    def test_with_region_prefix(self):
        region, query = _parse_query("fr-fr:intelligence artificielle")
        assert region == "fr-fr"
        assert query == "intelligence artificielle"

    def test_without_region(self):
        region, query = _parse_query("artificial intelligence")
        assert region == "wt-wt"
        assert query == "artificial intelligence"

    def test_case_insensitive_region(self):
        region, query = _parse_query("DE-DE:künstliche Intelligenz")
        assert region == "de-de"
        assert query == "künstliche Intelligenz"

    def test_strips_whitespace(self):
        region, query = _parse_query("  us-en:  test query  ")
        assert region == "us-en"
        assert query == "test query"

    def test_colon_in_query_preserved(self):
        """Only the first region:query split matters — colons in query are ok."""
        region, query = _parse_query("fr-fr:site:lemonde.fr AI")
        assert region == "fr-fr"
        assert query == "site:lemonde.fr AI"


class TestSearchRegion:
    """Test per-region search."""

    @patch("translate_search.DDGS")
    def test_tags_results_with_region(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.return_value = [
            {
                "title": "Résultat",
                "url": "https://lemonde.fr/article",
                "body": "Description en français",
                "date": "2026-03-11",
                "source": "Le Monde",
            }
        ]

        results = _search_region("test", "fr-fr", "news", 10)

        assert len(results) == 1
        assert results[0]["region"] == "fr-fr"
        assert results[0]["language"] == "French"

    @patch("translate_search.DDGS")
    def test_passes_region_to_ddgs(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.return_value = []

        _search_region("query", "de-de", "news", 15)

        mock_ddgs.news.assert_called_once_with(
            "query", max_results=15, region="de-de"
        )

    @patch("translate_search.DDGS")
    def test_text_search_type(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.text.return_value = [
            {
                "title": "Result",
                "href": "https://example.com/page",
                "body": "Description",
            }
        ]

        results = _search_region("query", "us-en", "text", 10)

        assert len(results) == 1
        mock_ddgs.text.assert_called_once()
        # Text results should not have date/source
        assert "date" not in results[0]

    @patch("translate_search.DDGS")
    def test_handles_api_error(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.side_effect = Exception("Failed")

        results = _search_region("query", "fr-fr", "news", 10)

        assert results == []


class TestMultiRegionSearchPreconditions:
    """Test input validation via @precondition."""

    def test_empty_queries_raises(self):
        with pytest.raises(ContractViolationError, match="(?i)at least one"):
            multi_region_search([])


class TestMultiRegionSearch:
    """Test multi-region search orchestration."""

    @patch("translate_search._search_region")
    def test_combines_results_from_regions(self, mock_search):
        mock_search.side_effect = [
            [
                {
                    "title": "French Result",
                    "url": "https://lemonde.fr/a",
                    "description": "Desc",
                    "region": "fr-fr",
                    "language": "French",
                }
            ],
            [
                {
                    "title": "German Result",
                    "url": "https://spiegel.de/a",
                    "description": "Desc",
                    "region": "de-de",
                    "language": "German",
                }
            ],
        ]

        results = multi_region_search([
            "fr-fr:intelligence artificielle",
            "de-de:künstliche Intelligenz",
        ])

        assert len(results) == 2
        regions = {r["region"] for r in results}
        assert "fr-fr" in regions
        assert "de-de" in regions

    @patch("translate_search._search_region")
    def test_deduplicates_across_regions(self, mock_search):
        mock_search.side_effect = [
            [
                {
                    "title": "Same",
                    "url": "https://example.com/a",
                    "description": "",
                    "region": "us-en",
                    "language": "English (US)",
                }
            ],
            [
                {
                    "title": "Same",
                    "url": "https://example.com/a",
                    "description": "",
                    "region": "uk-en",
                    "language": "English (UK)",
                }
            ],
        ]

        results = multi_region_search(["us-en:test", "uk-en:test"])

        assert len(results) == 1

    @patch("translate_search._search_region")
    def test_handles_search_failure(self, mock_search):
        mock_search.side_effect = [
            Exception("Failed"),
            [
                {
                    "title": "OK",
                    "url": "https://example.com/ok",
                    "description": "",
                    "region": "de-de",
                    "language": "German",
                }
            ],
        ]

        results = multi_region_search(["fr-fr:test", "de-de:test"])

        assert len(results) == 1
        assert results[0]["region"] == "de-de"
