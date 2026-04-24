"""Tests for kb page_query.py — reopen narrow slices from markdown/text artifacts."""

from __future__ import annotations

import importlib.util
import json
import sys
import textwrap
from pathlib import Path


def _load_module():
    script_dir = Path(__file__).resolve().parent.parent / "scripts"
    script_path = script_dir / "page_query.py"
    spec = importlib.util.spec_from_file_location("kb_page_query", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, str(script_dir))
    spec.loader.exec_module(module)
    return module


page_query = _load_module()


def _sample_markdown() -> str:
    return textwrap.dedent(
        """\
        # Source Analysis
        Intro line
        Another intro line

        ## Hidden Gems
        Gem 1
        Gem 2
        Gem 3

        ## Questions
        Question 1
        Question 2
        """
    )


class TestQueryMarkdownPage:
    def test_selects_section_by_heading(self, tmp_path: Path):
        page_path = tmp_path / "analysis.md"
        page_path.write_text(_sample_markdown(), encoding="utf-8")

        result = page_query.query_markdown_page(page_path, heading="Hidden Gems")

        assert result["mode"] == "heading"
        assert result["heading"] == "Hidden Gems"
        assert "Gem 1" in result["content"]
        assert "Question 1" not in result["content"]

    def test_selects_line_range(self, tmp_path: Path):
        page_path = tmp_path / "analysis.md"
        page_path.write_text(_sample_markdown(), encoding="utf-8")

        result = page_query.query_markdown_page(page_path, start_line=6, end_line=8)

        assert result["mode"] == "lines"
        assert result["content"] == "Gem 1\nGem 2\nGem 3"

    def test_selects_fixed_size_chunk(self, tmp_path: Path):
        page_path = tmp_path / "analysis.md"
        page_path.write_text(_sample_markdown(), encoding="utf-8")

        result = page_query.query_markdown_page(page_path, chunk=2, chunk_size=4)

        assert result["mode"] == "chunk"
        assert result["chunk"] == 2
        assert result["chunk_count"] == 3
        assert result["start_line"] == 5
        assert result["end_line"] == 8
        assert "## Hidden Gems" in result["content"]


class TestPageQueryCli:
    def test_main_writes_output_file_and_returns_envelope(self, tmp_path: Path, capsys):
        page_path = tmp_path / "analysis.md"
        page_path.write_text(_sample_markdown(), encoding="utf-8")
        output_path = tmp_path / "page-slice.json"

        page_query.main([
            "--file",
            str(page_path),
            "--heading",
            "Questions",
            "--output",
            str(output_path),
        ])

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "kb-page-query"
        assert envelope["top_level_type"] == "object"
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["heading"] == "Questions"
        assert "Question 1" in payload["content"]