"""Tests for open.py — load KB context for LLM priming."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from ._loader import load_script_module

init = load_script_module("kb_test_open_init", "init.py")
open_kb = load_script_module("kb_test_open_script", "open.py")
state = load_script_module("kb_test_open_state", "state.py")
ContractViolationError = open_kb.ContractViolationError


@pytest.fixture
def kb_path(tmp_path: Path) -> Path:
    p = tmp_path / "test-kb"
    init.scaffold_kb(str(p), "Test KB")
    return p


class TestOpenKb:
    def test_returns_config(self, kb_path: Path):
        result = open_kb.open_kb(str(kb_path))
        assert result["name"] == "Test KB"
        assert result["kb_path"] == str(kb_path)

    def test_returns_rules(self, kb_path: Path):
        result = open_kb.open_kb(str(kb_path))
        assert "rules" in result
        assert len(result["rules"]) > 50

    def test_returns_index(self, kb_path: Path):
        result = open_kb.open_kb(str(kb_path))
        assert "index" in result
        assert "Index" in result["index"]

    def test_returns_file_counts(self, kb_path: Path):
        result = open_kb.open_kb(str(kb_path))
        counts = result["file_counts"]
        assert "entities" in counts
        assert "topics" in counts
        assert "ideas" in counts
        assert "citations" in counts
        assert "controversies" in counts

    def test_returns_recent_log(self, kb_path: Path):
        result = open_kb.open_kb(str(kb_path))
        assert "recent_log" in result
        assert "init" in result["recent_log"]

    def test_returns_pending_tasks(self, kb_path: Path):
        result = open_kb.open_kb(str(kb_path))
        assert "pending_tasks" in result
        assert result["pending_tasks"] == []

    def test_detects_pending_tasks(self, kb_path: Path):
        state.init_task(
            "t1", "add", "Ingest paper", str(kb_path),
            state_dir=kb_path / ".kb" / "tasks",
        )
        result = open_kb.open_kb(str(kb_path))
        assert len(result["pending_tasks"]) == 1
        assert result["pending_tasks"][0]["task_id"] == "t1"

    def test_rejects_nonexistent_kb(self, tmp_path: Path):
        with pytest.raises(ContractViolationError, match="not found"):
            open_kb.open_kb(str(tmp_path / "nonexistent"))

    def test_rejects_non_kb_directory(self, tmp_path: Path):
        (tmp_path / "not-a-kb").mkdir()
        with pytest.raises(ContractViolationError, match="(?i)not a valid KB"):
            open_kb.open_kb(str(tmp_path / "not-a-kb"))

    def test_returns_source_count(self, kb_path: Path):
        result = open_kb.open_kb(str(kb_path))
        assert result["total_sources"] == 0

    def test_stats_mode(self, kb_path: Path):
        result = open_kb.open_kb(str(kb_path), stats=True)
        assert "total_files" in result
        assert "total_links" in result


class TestCli:
    def test_open_cli(self, kb_path: Path, capsys):
        open_kb.main(["--path", str(kb_path)])
        out = json.loads(capsys.readouterr().out)
        assert out["name"] == "Test KB"

    def test_stats_cli(self, kb_path: Path, capsys):
        open_kb.main(["--path", str(kb_path), "--stats"])
        out = json.loads(capsys.readouterr().out)
        assert "total_files" in out
