"""Tests for page_query.py — reopen narrow slices from markdown pages."""

from __future__ import annotations

import json
import os
import sys
import textwrap
import importlib.util
from pathlib import Path


def _load_page_query_module():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "page_query.py"
    spec = importlib.util.spec_from_file_location("duckduckgo_page_query", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    spec.loader.exec_module(module)
    return module


page_query = _load_page_query_module()


def _sample_markdown() -> str:
    return textwrap.dedent(
        """\
        # Trip Plan
        Intro line 1
        Intro line 2

        ## Transport
        Train line 1
        Train line 2
        Train line 3

        ## Budget
        Budget line 1
        Budget line 2
        Budget line 3
        """
    )


class TestQueryMarkdownPage:
    def test_selects_section_by_heading(self, tmp_path: Path):
        page_path = tmp_path / "page.md"
        page_path.write_text(_sample_markdown(), encoding="utf-8")

        result = page_query.query_markdown_page(page_path, heading="Transport")

        assert result["mode"] == "heading"
        assert result["heading"] == "Transport"
        assert "Train line 1" in result["content"]
        assert "Budget line 1" not in result["content"]

    def test_selects_line_range(self, tmp_path: Path):
        page_path = tmp_path / "page.md"
        page_path.write_text(_sample_markdown(), encoding="utf-8")

        result = page_query.query_markdown_page(page_path, start_line=6, end_line=8)

        assert result["mode"] == "lines"
        assert result["start_line"] == 6
        assert result["end_line"] == 8
        assert result["content"] == "Train line 1\nTrain line 2\nTrain line 3"

    def test_selects_fixed_size_chunk(self, tmp_path: Path):
        page_path = tmp_path / "page.md"
        page_path.write_text(_sample_markdown(), encoding="utf-8")

        result = page_query.query_markdown_page(page_path, chunk=2, chunk_size=4)

        assert result["mode"] == "chunk"
        assert result["chunk"] == 2
        assert result["chunk_count"] == 4
        assert result["start_line"] == 5
        assert result["end_line"] == 8
        assert "## Transport" in result["content"]
        assert "Train line 3" in result["content"]


class TestPageQueryCli:
    def test_main_writes_output_file_and_returns_envelope(self, tmp_path: Path, capsys):
        page_path = tmp_path / "page.md"
        page_path.write_text(_sample_markdown(), encoding="utf-8")
        output_path = tmp_path / "page-slice.json"

        page_query.main([
            "--file",
            str(page_path),
            "--heading",
            "Budget",
            "--output",
            str(output_path),
        ])

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "duckduckgo-page-query"
        assert envelope["top_level_type"] == "object"
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["heading"] == "Budget"
        assert "Budget line 1" in payload["content"]