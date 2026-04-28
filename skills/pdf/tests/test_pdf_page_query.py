# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pytest >= 8.0",
# ]
# ///
"""Tests for pdf page_query helper."""

from __future__ import annotations

import importlib.util
import json
import textwrap
from pathlib import Path


def _load_page_query_module():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "page_query.py"
    spec = importlib.util.spec_from_file_location("pdf_page_query", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


page_query = _load_page_query_module()


def _sample_markdown() -> str:
    return textwrap.dedent(
        """\
        # Overview
        Intro line one
        Intro line two

        ## Findings
        Evidence line 1
        Evidence line 2
        Evidence line 3

        ## Risks
        Risk line 1
        Risk line 2
        """
    )


class TestPdfPageQuery:
    def test_select_by_heading(self, tmp_path: Path):
        page = tmp_path / "page.md"
        page.write_text(_sample_markdown(), encoding="utf-8")

        result = page_query.query_markdown_page(page, heading="Findings")

        assert result["mode"] == "heading"
        assert result["heading"] == "Findings"
        assert "Evidence line 1" in result["content"]
        assert "Risk line 1" not in result["content"]

    def test_select_by_line_range(self, tmp_path: Path):
        page = tmp_path / "page.md"
        page.write_text(_sample_markdown(), encoding="utf-8")

        result = page_query.query_markdown_page(page, start_line=6, end_line=8)

        assert result["mode"] == "lines"
        assert result["content"] == "Evidence line 1\nEvidence line 2\nEvidence line 3"

    def test_select_by_chunk(self, tmp_path: Path):
        page = tmp_path / "page.md"
        page.write_text(_sample_markdown(), encoding="utf-8")

        result = page_query.query_markdown_page(page, chunk=2, chunk_size=4)

        assert result["mode"] == "chunk"
        assert result["chunk"] == 2
        assert result["start_line"] == 5
        assert result["end_line"] == 8
        assert "## Findings" in result["content"]

    def test_cli_output_writes_artifact_and_returns_envelope(self, tmp_path: Path, capsys):
        page = tmp_path / "page.md"
        page.write_text(_sample_markdown(), encoding="utf-8")
        output_path = tmp_path / "slice.json"

        page_query.main([
            "--file",
            str(page),
            "--heading",
            "Risks",
            "--output",
            str(output_path),
        ])

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "pdf-page-query"
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["heading"] == "Risks"
        assert "Risk line 1" in payload["content"]
