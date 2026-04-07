"""Tests for init.py — KB scaffolding."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import init
from contracts import ContractViolationError


@pytest.fixture
def kb_path(tmp_path: Path) -> Path:
    return tmp_path / "my-kb"


class TestScaffoldKb:
    def test_creates_directory_structure(self, kb_path: Path):
        init.scaffold_kb(str(kb_path), "My Knowledge Base")
        assert (kb_path / ".kb" / "config.yaml").exists()
        assert (kb_path / ".kb" / "rules.md").exists()
        assert (kb_path / ".kb" / "tasks").is_dir()
        assert (kb_path / "sources" / "files").is_dir()
        assert (kb_path / "sources" / "references").is_dir()
        assert (kb_path / "knowledge" / "entities").is_dir()
        assert (kb_path / "knowledge" / "topics").is_dir()
        assert (kb_path / "knowledge" / "ideas").is_dir()
        assert (kb_path / "knowledge" / "locations").is_dir()
        assert (kb_path / "knowledge" / "timeline" / "years").is_dir()
        assert (kb_path / "knowledge" / "timeline" / "months").is_dir()
        assert (kb_path / "knowledge" / "timeline" / "days").is_dir()
        assert (kb_path / "knowledge" / "sources").is_dir()
        assert (kb_path / "knowledge" / "citations").is_dir()
        assert (kb_path / "knowledge" / "controversies").is_dir()
        assert (kb_path / "knowledge" / "meta").is_dir()
        assert (kb_path / "index.md").exists()
        assert (kb_path / "log.md").exists()

    def test_config_yaml_content(self, kb_path: Path):
        init.scaffold_kb(str(kb_path), "My Knowledge Base")
        config = yaml.safe_load((kb_path / ".kb" / "config.yaml").read_text())
        assert config["name"] == "My Knowledge Base"
        assert "created" in config
        assert config["version"] == 1
        assert config["link_format"] == "wikilink"

    def test_rules_md_is_non_empty(self, kb_path: Path):
        init.scaffold_kb(str(kb_path), "My Knowledge Base")
        rules = (kb_path / ".kb" / "rules.md").read_text()
        assert len(rules) > 100  # Non-trivial rules doc
        assert "wikilink" in rules.lower() or "[[" in rules

    def test_index_md_has_header(self, kb_path: Path):
        init.scaffold_kb(str(kb_path), "My Knowledge Base")
        index = (kb_path / "index.md").read_text()
        assert "# " in index

    def test_log_md_has_header(self, kb_path: Path):
        init.scaffold_kb(str(kb_path), "My Knowledge Base")
        log = (kb_path / "log.md").read_text()
        assert "# " in log

    def test_returns_kb_path_and_config(self, kb_path: Path):
        result = init.scaffold_kb(str(kb_path), "My Knowledge Base")
        assert result["kb_path"] == str(kb_path)
        assert result["name"] == "My Knowledge Base"

    def test_rejects_empty_name(self, kb_path: Path):
        with pytest.raises(ContractViolationError, match="name"):
            init.scaffold_kb(str(kb_path), "")

    def test_rejects_empty_path(self, kb_path: Path):
        with pytest.raises(ContractViolationError, match="kb_path"):
            init.scaffold_kb("", "Name")

    def test_rejects_existing_kb(self, kb_path: Path):
        init.scaffold_kb(str(kb_path), "First")
        with pytest.raises(ContractViolationError, match="already exists"):
            init.scaffold_kb(str(kb_path), "Second")

    def test_source_registry_in_config(self, kb_path: Path):
        init.scaffold_kb(str(kb_path), "Test KB")
        config = yaml.safe_load((kb_path / ".kb" / "config.yaml").read_text())
        assert "next_source_id" not in config
        assert config["sources"] == []


class TestCli:
    def test_init_cli(self, kb_path: Path, capsys):
        init.main(["--path", str(kb_path), "--name", "CLI KB"])
        out = json.loads(capsys.readouterr().out)
        assert out["name"] == "CLI KB"
        assert (kb_path / ".kb" / "config.yaml").exists()
