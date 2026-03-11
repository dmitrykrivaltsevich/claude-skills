"""Tests for fact_check.py — claim cross-referencing."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from contracts import ContractViolationError
from fact_check import SOURCE_TIERS, _search_tier, cross_reference


class TestCrossReferencePreconditions:
    """Test claim validation via @precondition."""

    def test_short_claim_raises(self):
        with pytest.raises(ContractViolationError, match="at least 5"):
            cross_reference("hi")

    def test_whitespace_only_raises(self):
        with pytest.raises(ContractViolationError, match="at least 5"):
            cross_reference("    ")


class TestSearchTier:
    """Test per-tier searching."""

    @patch("fact_check.DDGS")
    def test_returns_structured_tier_data(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.return_value = [
            {
                "title": "Wire Story",
                "url": "https://reuters.com/story",
                "source": "Reuters",
                "date": "2026-03-11",
                "body": "Detailed reporting on the claim.",
            }
        ]

        result = _search_tier("test claim here", "wires", ["site:reuters.com"])

        assert result["tier"] == "wires"
        assert result["result_count"] >= 1
        assert result["results"][0]["source"] == "Reuters"

    @patch("fact_check.DDGS")
    def test_deduplicates_within_tier(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        # Same URL returned from two different site queries
        mock_ddgs.news.return_value = [
            {
                "title": "Same Story",
                "url": "https://example.com/same",
                "source": "Ex",
                "date": "",
                "body": "",
            },
        ]

        result = _search_tier(
            "claim",
            "wires",
            ["site:reuters.com", "site:apnews.com"],
        )

        assert result["result_count"] == 1

    @patch("fact_check.DDGS")
    def test_handles_api_error(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.side_effect = Exception("Rate limited")

        result = _search_tier("claim", "wires", ["site:reuters.com"])

        assert result["tier"] == "wires"
        assert result["result_count"] == 0

    @patch("fact_check.DDGS")
    def test_truncates_descriptions(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.return_value = [
            {
                "title": "Long",
                "url": "https://example.com/long",
                "source": "Ex",
                "date": "",
                "body": "x" * 2000,
            }
        ]

        result = _search_tier("claim", "wires", ["site:reuters.com"])

        assert len(result["results"][0]["description"]) <= 500


class TestCrossReference:
    """Test full cross-referencing."""

    @patch("fact_check._search_tier")
    def test_returns_all_requested_tiers(self, mock_search):
        mock_search.return_value = {
            "tier": "mock",
            "result_count": 1,
            "results": [{"title": "R"}],
        }

        result = cross_reference(
            "test claim long enough",
            tiers=["wires", "broadsheets"],
        )

        assert result["tiers_checked"] == 2

    @patch("fact_check._search_tier")
    def test_summary_counts(self, mock_search):
        mock_search.side_effect = [
            {"tier": "wires", "result_count": 3, "results": [{}] * 3},
            {"tier": "broadsheets", "result_count": 0, "results": []},
        ]

        result = cross_reference(
            "important claim here",
            tiers=["wires", "broadsheets"],
        )

        assert result["total_results"] == 3
        assert result["tiers_with_coverage"] == 1

    @patch("fact_check._search_tier")
    def test_includes_claim_in_output(self, mock_search):
        mock_search.return_value = {
            "tier": "wires",
            "result_count": 0,
            "results": [],
        }

        result = cross_reference("specific claim text", tiers=["wires"])

        assert result["claim"] == "specific claim text"

    @patch("fact_check._search_tier")
    def test_defaults_to_all_tiers(self, mock_search):
        mock_search.return_value = {
            "tier": "any",
            "result_count": 0,
            "results": [],
        }

        result = cross_reference("claim with no tier filter")

        assert result["tiers_checked"] == len(SOURCE_TIERS)

    @patch("fact_check._search_tier")
    def test_ignores_unknown_tiers(self, mock_search):
        mock_search.return_value = {
            "tier": "wires",
            "result_count": 0,
            "results": [],
        }

        result = cross_reference(
            "claim for testing",
            tiers=["wires", "nonexistent_tier"],
        )

        # Only "wires" should be searched
        assert result["tiers_checked"] == 1
