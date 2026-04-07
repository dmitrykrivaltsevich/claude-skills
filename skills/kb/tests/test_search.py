"""Tests for search.py — full-text search across KB files."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import init
import search
from contracts import ContractViolationError


@pytest.fixture
def kb_path(tmp_path: Path) -> Path:
    p = tmp_path / "test-kb"
    init.scaffold_kb(str(p), "Test KB")
    return p


def _write_entry(kb_path: Path, rel_path: str, content: str) -> Path:
    f = kb_path / rel_path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    return f


class TestSearch:
    def test_finds_matching_files(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/topics/quantum.md",
                     "# Quantum Computing\n\nQuantum supremacy achieved.")
        _write_entry(kb_path, "knowledge/topics/classical.md",
                     "# Classical Computing\n\nTraditional approach.")
        result = search.search_kb(str(kb_path), "quantum")
        assert len(result["matches"]) >= 1
        assert any("quantum.md" in m["file"] for m in result["matches"])

    def test_returns_context_lines(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/topics/quantum.md",
                     "# Quantum Computing\n\nQuantum supremacy achieved in 2024.")
        result = search.search_kb(str(kb_path), "supremacy")
        assert len(result["matches"]) == 1
        assert "supremacy" in result["matches"][0]["context"]

    def test_case_insensitive(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/topics/ai.md",
                     "# AI Safety\n\nArtificial Intelligence risks.")
        result = search.search_kb(str(kb_path), "artificial intelligence")
        assert len(result["matches"]) >= 1

    def test_no_matches(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/topics/ai.md", "# AI\n\nContent.")
        result = search.search_kb(str(kb_path), "nonexistent-term-xyz")
        assert len(result["matches"]) == 0

    def test_searches_sources_too(self, kb_path: Path):
        _write_entry(kb_path, "sources/references/src-001.md",
                     "# Source\n\nRare keyword bioluminescence.")
        result = search.search_kb(str(kb_path), "bioluminescence")
        assert len(result["matches"]) >= 1

    def test_excludes_kb_dot_dir(self, kb_path: Path):
        _write_entry(kb_path, ".kb/rules.md",
                     "# Rules\n\nSearchable keyword unicorn.")
        # Also add to knowledge so we have something to find
        _write_entry(kb_path, "knowledge/topics/test.md", "# Test\n\nContent.")
        result = search.search_kb(str(kb_path), "unicorn")
        # .kb/ files should not appear in search results
        for m in result["matches"]:
            assert ".kb/" not in m["file"]

    def test_limit(self, kb_path: Path):
        for i in range(20):
            _write_entry(kb_path, f"knowledge/topics/topic-{i}.md",
                         f"# Topic {i}\n\nCommon keyword repeated here.")
        result = search.search_kb(str(kb_path), "common keyword", limit=5)
        assert len(result["matches"]) == 5

    def test_rejects_empty_query(self, kb_path: Path):
        with pytest.raises(ContractViolationError, match="query"):
            search.search_kb(str(kb_path), "")


class TestCli:
    def test_search_cli(self, kb_path: Path, capsys):
        _write_entry(kb_path, "knowledge/topics/test.md",
                     "# Test\n\nFindable content.")
        search.main(["--path", str(kb_path), "--query", "findable"])
        out = json.loads(capsys.readouterr().out)
        assert len(out["matches"]) >= 1
