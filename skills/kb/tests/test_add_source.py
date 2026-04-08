"""Tests for add_source.py — register source files in KB."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import add_source
import init
from contracts import ContractViolationError


@pytest.fixture
def kb_path(tmp_path: Path) -> Path:
    p = tmp_path / "test-kb"
    init.scaffold_kb(str(p), "Test KB")
    return p


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "paper.pdf"
    p.write_bytes(b"%PDF-1.4 fake pdf content")
    return p


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    p = tmp_path / "article.md"
    p.write_text("# Great Article\n\nSome content here.", encoding="utf-8")
    return p


class TestRegisterFile:
    def test_copies_file_to_sources(self, kb_path: Path, sample_pdf: Path):
        result = add_source.register_source(str(kb_path), str(sample_pdf), source_id="real-2020")
        src_dir = kb_path / "sources" / "files" / "real-2020"
        assert src_dir.exists()
        assert (src_dir / "paper.pdf").exists()

    def test_returns_source_id(self, kb_path: Path, sample_pdf: Path):
        result = add_source.register_source(str(kb_path), str(sample_pdf), source_id="real-2020")
        assert result["source_id"] == "real-2020"

    def test_rejects_duplicate_source_id(self, kb_path: Path, sample_pdf: Path, sample_md: Path):
        add_source.register_source(str(kb_path), str(sample_pdf), source_id="real-2020")
        with pytest.raises(ContractViolationError, match="already registered"):
            add_source.register_source(str(kb_path), str(sample_md), source_id="real-2020")

    def test_rejects_invalid_source_id_format(self, kb_path: Path, sample_pdf: Path):
        with pytest.raises(ContractViolationError, match="source_id"):
            add_source.register_source(str(kb_path), str(sample_pdf), source_id="SRC 001!")

    def test_rejects_empty_source_id(self, kb_path: Path, sample_pdf: Path):
        with pytest.raises(ContractViolationError, match="source_id"):
            add_source.register_source(str(kb_path), str(sample_pdf), source_id="")

    def test_updates_config_registry(self, kb_path: Path, sample_pdf: Path):
        add_source.register_source(str(kb_path), str(sample_pdf), source_id="real-2020")
        config = yaml.safe_load(
            (kb_path / ".kb" / "config.yaml").read_text(encoding="utf-8")
        )
        assert len(config["sources"]) == 1
        assert config["sources"][0]["id"] == "real-2020"
        assert config["sources"][0]["original_name"] == "paper.pdf"
        assert "next_source_id" not in config

    def test_returns_copied_path(self, kb_path: Path, sample_pdf: Path):
        result = add_source.register_source(str(kb_path), str(sample_pdf), source_id="real-2020")
        assert result["copied_to"] == str(
            kb_path / "sources" / "files" / "real-2020" / "paper.pdf"
        )

    def test_preserves_original_content(self, kb_path: Path, sample_pdf: Path):
        result = add_source.register_source(str(kb_path), str(sample_pdf), source_id="real-2020")
        copied = Path(result["copied_to"])
        assert copied.read_bytes() == b"%PDF-1.4 fake pdf content"

    def test_rejects_empty_kb_path(self, sample_pdf: Path):
        with pytest.raises(ContractViolationError, match="kb_path"):
            add_source.register_source("", str(sample_pdf), source_id="real-2020")

    def test_rejects_nonexistent_source(self, kb_path: Path):
        with pytest.raises(ContractViolationError, match="not found"):
            add_source.register_source(str(kb_path), "/nonexistent/file.pdf", source_id="real-2020")

    def test_allows_disambiguated_ids(self, kb_path: Path, sample_pdf: Path, sample_md: Path):
        """Same author-year with letter suffix for disambiguation."""
        add_source.register_source(str(kb_path), str(sample_pdf), source_id="real-2020a")
        result = add_source.register_source(str(kb_path), str(sample_md), source_id="real-2020b")
        assert result["source_id"] == "real-2020b"

    def test_creates_stub_for_local_file(self, kb_path: Path, sample_pdf: Path):
        """Local file registration must create a navigable .md stub like references do."""
        add_source.register_source(str(kb_path), str(sample_pdf), source_id="real-2020")
        stub = kb_path / "sources" / "files" / "real-2020.md"
        assert stub.exists()
        content = stub.read_text(encoding="utf-8")
        assert "[[real-2020-analysis]]" in content
        assert "paper.pdf" in content


class TestRegisterReference:
    def test_creates_reference_stub(self, kb_path: Path):
        result = add_source.register_source(
            str(kb_path), "https://example.com/paper.pdf",
            is_reference=True, title="Remote Paper", source_id="smith-2024",
        )
        stub = kb_path / "sources" / "references" / "smith-2024.md"
        assert stub.exists()
        content = stub.read_text(encoding="utf-8")
        assert "https://example.com/paper.pdf" in content
        assert "Remote Paper" in content
        assert "[[smith-2024-analysis]]" in content

    def test_reference_updates_config(self, kb_path: Path):
        result = add_source.register_source(
            str(kb_path), "https://example.com/paper.pdf",
            is_reference=True, title="Remote Paper", source_id="smith-2024",
        )
        config = yaml.safe_load(
            (kb_path / ".kb" / "config.yaml").read_text(encoding="utf-8")
        )
        assert config["sources"][0]["type"] == "reference"
        assert config["sources"][0]["id"] == "smith-2024"
        assert config["sources"][0]["location"] == "https://example.com/paper.pdf"


class TestCli:
    def test_register_file_cli(self, kb_path: Path, sample_pdf: Path, capsys):
        add_source.main([
            "--kb-path", str(kb_path),
            "--source", str(sample_pdf),
            "--source-id", "real-2020",
        ])
        out = json.loads(capsys.readouterr().out)
        assert out["source_id"] == "real-2020"

    def test_register_reference_cli(self, kb_path: Path, capsys):
        add_source.main([
            "--kb-path", str(kb_path),
            "--source", "https://example.com/doc",
            "--reference",
            "--title", "Some Doc",
            "--source-id", "jones-2023",
        ])
        out = json.loads(capsys.readouterr().out)
        assert out["source_id"] == "jones-2023"
        assert out["type"] == "reference"
