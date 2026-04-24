"""CLI tests for duckduckgo artifact mode."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import fact_check
import search
import top_news


class TestSearchArtifactMode:
    @patch("search.DDGS")
    def test_main_writes_output_file_and_returns_envelope(
        self, mock_ddgs_cls, monkeypatch, capsys, tmp_path: Path
    ):
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

        output_path = tmp_path / "news.json"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "search.py",
                "news",
                "--query",
                "technology",
                "--output",
                str(output_path),
            ],
        )

        search.main()

        captured = capsys.readouterr()
        envelope = json.loads(captured.out)

        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "duckduckgo-search-results"
        assert envelope["top_level_type"] == "array"
        assert envelope["item_count"] == 1
        assert json.loads(output_path.read_text(encoding="utf-8"))[0]["title"] == "Tech News"


class TestTopNewsArtifactMode:
    def test_main_writes_output_file_and_returns_envelope(
        self, monkeypatch, capsys, tmp_path: Path
    ):
        output_path = tmp_path / "top-news.json"
        monkeypatch.setattr(
            sys,
            "argv",
            ["top_news.py", "--output", str(output_path)],
        )

        with patch.object(top_news, "fetch_news", return_value=[
            {
                "title": "Story",
                "url": "https://example.com/story",
                "source": "Example News",
                "date": "2026-03-11",
                "description": "Story body",
                "author": "Author Name",
                "query_group": "broad",
            }
        ]), patch.object(top_news.random, "shuffle"):
            top_news.main()

        captured = capsys.readouterr()
        envelope = json.loads(captured.out)

        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "duckduckgo-top-news"
        assert envelope["top_level_type"] == "array"
        assert envelope["item_count"] == 1
        assert json.loads(output_path.read_text(encoding="utf-8"))[0]["title"] == "Story"


class TestFactCheckArtifactMode:
    def test_main_writes_output_file_and_returns_envelope(
        self, monkeypatch, capsys, tmp_path: Path
    ):
        output_path = tmp_path / "fact-check.json"
        monkeypatch.setattr(
            sys,
            "argv",
            ["fact_check.py", "test claim here", "--output", str(output_path)],
        )

        with patch.object(fact_check, "cross_reference", return_value={
            "claim": "test claim here",
            "tiers_checked": 2,
            "tiers_with_coverage": 1,
            "total_results": 3,
            "tiers": [],
        }):
            fact_check.main()

        captured = capsys.readouterr()
        envelope = json.loads(captured.out)

        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "duckduckgo-fact-check"
        assert envelope["top_level_type"] == "object"
        assert envelope["keys"] == ["claim", "tiers", "tiers_checked", "tiers_with_coverage", "total_results"]
        assert json.loads(output_path.read_text(encoding="utf-8"))["claim"] == "test claim here"