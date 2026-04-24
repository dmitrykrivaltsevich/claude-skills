"""Tests for related.py — find KB entries matching keywords."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ._loader import load_script_module

init = load_script_module("kb_test_related_init", "init.py")
related = load_script_module("kb_test_related_script", "related.py")
ContractViolationError = related.ContractViolationError


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


class TestFindRelated:
    def test_finds_entries_matching_single_keyword(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/topics/quantum.md",
                     "---\ntype: topic\n---\n# Quantum Computing\n\nQuantum stuff.")
        _write_entry(kb_path, "knowledge/topics/classical.md",
                     "---\ntype: topic\n---\n# Classical\n\nNo match here.")
        result = related.find_related(str(kb_path), ["quantum"])
        assert len(result["entries"]) == 1
        assert "quantum.md" in result["entries"][0]["file"]
        assert result["entries"][0]["overlap"] == 1

    def test_scores_by_keyword_overlap(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/topics/full.md",
                     "---\ntype: topic\n---\n# Full\n\nQuantum computing with attention mechanisms.")
        _write_entry(kb_path, "knowledge/topics/partial.md",
                     "---\ntype: topic\n---\n# Partial\n\nOnly quantum here.")
        result = related.find_related(str(kb_path), ["quantum", "attention", "computing"])
        assert len(result["entries"]) == 2
        # Full match (3 keywords) ranks above partial (1 keyword)
        assert result["entries"][0]["overlap"] > result["entries"][1]["overlap"]
        assert "full.md" in result["entries"][0]["file"]

    def test_returns_matched_keywords(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/entities/feynman.md",
                     "---\ntype: entity\n---\n# Richard Feynman\n\nQuantum electrodynamics.")
        result = related.find_related(str(kb_path), ["feynman", "quantum", "biology"])
        assert len(result["entries"]) == 1
        matched = set(result["entries"][0]["matched_keywords"])
        assert "feynman" in matched
        assert "quantum" in matched
        assert "biology" not in matched

    def test_no_matches_returns_empty(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/topics/ai.md",
                     "---\ntype: topic\n---\n# AI\n\nContent.")
        result = related.find_related(str(kb_path), ["nonexistent123"])
        assert len(result["entries"]) == 0

    def test_category_filter(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/entities/feynman.md",
                     "---\ntype: entity\n---\n# Feynman\n\nQuantum expert.")
        _write_entry(kb_path, "knowledge/topics/quantum.md",
                     "---\ntype: topic\n---\n# Quantum\n\nQuantum topic.")
        result = related.find_related(str(kb_path), ["quantum"], category="entities")
        files = [e["file"] for e in result["entries"]]
        assert any("entities/" in f for f in files)
        assert not any("topics/" in f for f in files)

    def test_limit(self, kb_path: Path):
        for i in range(10):
            _write_entry(kb_path, f"knowledge/topics/topic-{i}.md",
                         f"---\ntype: topic\n---\n# Topic {i}\n\nKeyword alpha here.")
        result = related.find_related(str(kb_path), ["alpha"], limit=3)
        assert len(result["entries"]) == 3
        assert result["truncated"] is True

    def test_extracts_title_from_heading(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/ideas/cool-idea.md",
                     "---\ntype: idea\n---\n# My Cool Idea\n\nKeyword match here.")
        result = related.find_related(str(kb_path), ["keyword"])
        assert result["entries"][0]["title"] == "My Cool Idea"

    def test_case_insensitive(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/topics/mixed.md",
                     "---\ntype: topic\n---\n# Mixed Case\n\nQUANTUM Computing.")
        result = related.find_related(str(kb_path), ["quantum"])
        assert len(result["entries"]) == 1

    def test_rejects_empty_keywords(self, kb_path: Path):
        with pytest.raises(ContractViolationError, match="keywords"):
            related.find_related(str(kb_path), [])


class TestCli:
    def test_related_cli(self, kb_path: Path, capsys):
        _write_entry(kb_path, "knowledge/topics/test.md",
                     "---\ntype: topic\n---\n# Test\n\nFindable content.")
        related.main(["--kb-path", str(kb_path), "--keywords", "findable"])
        out = json.loads(capsys.readouterr().out)
        assert len(out["entries"]) >= 1

    def test_related_cli_with_category(self, kb_path: Path, capsys):
        _write_entry(kb_path, "knowledge/entities/someone.md",
                     "---\ntype: entity\n---\n# Someone\n\nImportant person.")
        related.main(["--kb-path", str(kb_path), "--keywords", "important",
                       "--category", "entities"])
        out = json.loads(capsys.readouterr().out)
        assert len(out["entries"]) >= 1
