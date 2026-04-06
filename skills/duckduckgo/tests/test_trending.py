"""Tests for trending.py — trend detection data pipe."""

import concurrent.futures
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from trending import _discover_topics, _gather_topic_data, gather_trends


class TestGatherTopicData:
    """Test per-topic data gathering."""

    @patch("trending.DDGS")
    def test_returns_structured_data(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.return_value = [
            {
                "title": "AI Regulation Update",
                "url": "https://example.com/ai",
                "source": "TechCrunch",
                "date": "2026-03-11T10:00:00",
                "body": "Story about AI",
            }
        ]
        mock_ddgs.suggestions.return_value = [
            {"phrase": "AI regulation"},
            {"phrase": "AI safety"},
        ]

        data = _gather_topic_data("AI")

        assert data["topic"] == "AI"
        assert isinstance(data["news_24h_count"], int)
        assert isinstance(data["news_7d_count"], int)
        assert isinstance(data["sources_24h"], list)
        assert isinstance(data["sample_headlines"], list)
        assert isinstance(data["related_queries"], list)
        assert "date_range" in data
        assert "earliest" in data["date_range"]
        assert "latest" in data["date_range"]

    @patch("trending.DDGS")
    def test_handles_api_errors(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.side_effect = Exception("Rate limited")
        mock_ddgs.suggestions.side_effect = Exception("Rate limited")

        data = _gather_topic_data("broken")

        assert data["topic"] == "broken"
        assert data["news_24h_count"] == 0
        assert data["news_7d_count"] == 0
        assert data["related_queries"] == []

    @patch("trending.DDGS")
    def test_excludes_topic_from_suggestions(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.news.return_value = []
        mock_ddgs.suggestions.return_value = [
            {"phrase": "climate"},  # same as topic — should be excluded
            {"phrase": "climate change"},
        ]

        data = _gather_topic_data("climate")

        assert "climate change" in data["related_queries"]
        # The exact topic should not appear
        assert "climate" not in data["related_queries"]


class TestGatherTrends:
    """Test parallel trend gathering."""

    @patch("trending._gather_topic_data")
    def test_gathers_multiple_topics(self, mock_gather):
        mock_gather.side_effect = lambda t: {
            "topic": t,
            "news_24h_count": 5,
            "news_7d_count": 10,
            "sources_24h": [],
            "source_count_24h": 0,
            "sample_headlines": [],
            "related_queries": [],
            "date_range": {"earliest": None, "latest": None},
        }

        results = gather_trends(["AI", "climate"], _executor_class=concurrent.futures.ThreadPoolExecutor)

        assert len(results) == 2
        topics = {r["topic"] for r in results}
        assert "AI" in topics
        assert "climate" in topics

    @patch("trending._gather_topic_data")
    def test_handles_individual_failures(self, mock_gather):
        def side_effect(t):
            if t == "broken":
                raise Exception("Failed")
            return {
                "topic": t,
                "news_24h_count": 3,
                "news_7d_count": 8,
                "sources_24h": [],
                "source_count_24h": 0,
                "sample_headlines": [],
                "related_queries": [],
                "date_range": {"earliest": None, "latest": None},
            }

        mock_gather.side_effect = side_effect

        results = gather_trends(["good", "broken"], _executor_class=concurrent.futures.ThreadPoolExecutor)

        assert len(results) == 2
        broken = [r for r in results if r["topic"] == "broken"][0]
        assert "error" in broken


class TestDiscoverTopics:
    """Test auto-discovery mode."""

    @patch("trending.DDGS")
    def test_returns_suggestions_from_seeds(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.suggestions.return_value = [
            {"phrase": "trending topic one"},
            {"phrase": "trending topic two"},
        ]

        topics = _discover_topics()

        assert len(topics) >= 1
        assert all(isinstance(t, str) for t in topics)

    @patch("trending.DDGS")
    def test_handles_all_seeds_failing(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        mock_ddgs.suggestions.side_effect = Exception("All failed")

        topics = _discover_topics()

        assert topics == []

    @patch("trending.DDGS")
    def test_deduplicates_suggestions(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value = mock_ddgs
        # Same suggestion from multiple seeds — should appear once
        mock_ddgs.suggestions.return_value = [{"phrase": "duplicate topic"}]

        topics = _discover_topics()

        assert topics.count("duplicate topic") == 1
