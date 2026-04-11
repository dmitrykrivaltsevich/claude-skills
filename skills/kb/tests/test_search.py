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
        assert len(result["results"]) >= 1
        assert any("quantum.md" in r["file"] for r in result["results"])

    def test_returns_context_lines(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/topics/quantum.md",
                     "# Quantum Computing\n\nQuantum supremacy achieved in 2024.")
        result = search.search_kb(str(kb_path), "supremacy")
        assert len(result["results"]) == 1
        assert "supremacy" in result["results"][0]["matches"][0]["context"]

    def test_case_insensitive(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/topics/ai.md",
                     "# AI Safety\n\nArtificial Intelligence risks.")
        result = search.search_kb(str(kb_path), "artificial intelligence")
        assert len(result["results"]) >= 1

    def test_no_matches(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/topics/ai.md", "# AI\n\nContent.")
        result = search.search_kb(str(kb_path), "nonexistent-term-xyz")
        assert len(result["results"]) == 0

    def test_searches_sources_too(self, kb_path: Path):
        _write_entry(kb_path, "sources/references/src-001.md",
                     "# Source\n\nRare keyword bioluminescence.")
        result = search.search_kb(str(kb_path), "bioluminescence")
        assert len(result["results"]) >= 1

    def test_excludes_kb_dot_dir(self, kb_path: Path):
        _write_entry(kb_path, ".kb/rules.md",
                     "# Rules\n\nSearchable keyword unicorn.")
        # Also add to knowledge so we have something to find
        _write_entry(kb_path, "knowledge/topics/test.md", "# Test\n\nContent.")
        result = search.search_kb(str(kb_path), "unicorn")
        # .kb/ files should not appear in search results
        for r in result["results"]:
            assert ".kb/" not in r["file"]

    def test_limit(self, kb_path: Path):
        for i in range(20):
            _write_entry(kb_path, f"knowledge/topics/topic-{i}.md",
                         f"# Topic {i}\n\nCommon keyword repeated here.")
        result = search.search_kb(str(kb_path), "common keyword", limit=5)
        assert len(result["results"]) == 5

    def test_rejects_empty_query(self, kb_path: Path):
        with pytest.raises(ContractViolationError, match="query"):
            search.search_kb(str(kb_path), "")

    def test_multiple_matches_per_file(self, kb_path: Path):
        """Default mode returns all matches per file, not just first."""
        _write_entry(kb_path, "knowledge/topics/multi.md",
                     "# Multi\n\nFirst mention of quantum.\n\nSecond mention of quantum.")
        result = search.search_kb(str(kb_path), "quantum")
        matching = [r for r in result["results"] if "multi.md" in r["file"]]
        assert len(matching) == 1
        assert matching[0]["hits"] == 2
        assert len(matching[0]["matches"]) == 2

    def test_first_only_flag(self, kb_path: Path):
        """--first-only returns only the first match per file."""
        _write_entry(kb_path, "knowledge/topics/multi.md",
                     "# Multi\n\nFirst mention of quantum.\n\nSecond mention of quantum.")
        result = search.search_kb(str(kb_path), "quantum", first_only=True)
        matching = [r for r in result["results"] if "multi.md" in r["file"]]
        assert len(matching) == 1
        assert matching[0]["hits"] == 1
        assert len(matching[0]["matches"]) == 1

    def test_category_filter(self, kb_path: Path):
        """--category restricts search to a specific knowledge subdirectory."""
        _write_entry(kb_path, "knowledge/topics/quantum.md",
                     "# Quantum\n\nTopic about quantum.")
        _write_entry(kb_path, "knowledge/entities/feynman.md",
                     "# Feynman\n\nQuantum expert.")
        result = search.search_kb(str(kb_path), "quantum", category="entities")
        files = [r["file"] for r in result["results"]]
        assert any("entities/" in f for f in files)
        assert not any("topics/" in f for f in files)

    def test_results_sorted_by_score(self, kb_path: Path):
        """Files with more matches / higher term coverage rank higher."""
        _write_entry(kb_path, "knowledge/topics/low.md",
                     "# Low\n\nOne mention of quantum.")
        _write_entry(kb_path, "knowledge/topics/high.md",
                     "# High\n\nQuantum quantum quantum quantum.\n\nMore quantum.")
        result = search.search_kb(str(kb_path), "quantum")
        assert len(result["results"]) >= 2
        # Higher-scoring file should be first
        assert result["results"][0]["score"] >= result["results"][1]["score"]

    def test_multi_term_coverage(self, kb_path: Path):
        """Multi-word queries score files by how many distinct terms appear."""
        _write_entry(kb_path, "knowledge/topics/partial.md",
                     "# Partial\n\nOnly quantum here.")
        _write_entry(kb_path, "knowledge/topics/full.md",
                     "# Full\n\nQuantum computing is powerful.")
        result = search.search_kb(str(kb_path), "quantum computing")
        full = [r for r in result["results"] if "full.md" in r["file"]]
        partial = [r for r in result["results"] if "partial.md" in r["file"]]
        assert len(full) == 1 and len(partial) == 1
        # Full match (2/2 terms) should outscore partial (1/2 terms)
        assert full[0]["score"] > partial[0]["score"]
        assert full[0]["term_coverage"] == "2/2"
        assert partial[0]["term_coverage"] == "1/2"


class TestCli:
    def test_search_cli(self, kb_path: Path, capsys):
        _write_entry(kb_path, "knowledge/topics/test.md",
                     "# Test\n\nFindable content.")
        search.main(["--path", str(kb_path), "--query", "findable"])
        out = json.loads(capsys.readouterr().out)
        assert len(out["results"]) >= 1

    def test_search_cli_with_category(self, kb_path: Path, capsys):
        _write_entry(kb_path, "knowledge/entities/person.md",
                     "# Person\n\nSomebody here.")
        search.main(["--path", str(kb_path), "--query", "somebody",
                      "--category", "entities"])
        out = json.loads(capsys.readouterr().out)
        assert len(out["results"]) >= 1
