"""Tests for add_source.py — register source files in KB."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from ._loader import load_script_module

add_source = load_script_module("kb_test_add_source_script", "add_source.py")
init = load_script_module("kb_test_add_source_init", "init.py")
ContractViolationError = add_source.ContractViolationError


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

    def test_reference_title_with_colon_produces_valid_yaml(self, kb_path: Path):
        """Title containing colons must produce valid YAML frontmatter."""
        add_source.register_source(
            str(kb_path),
            "https://example.com/paper.pdf",
            is_reference=True,
            title="Infrastructure: More, Better, Faster (Tang et al., 2010)",
            source_id="tang-2010",
        )
        stub = kb_path / "sources" / "references" / "tang-2010.md"
        content = stub.read_text(encoding="utf-8")
        # Must be parseable by YAML
        parts = content.split("---", 2)
        fm = yaml.safe_load(parts[1])
        assert fm["title"] == "Infrastructure: More, Better, Faster (Tang et al., 2010)"

    def test_file_title_with_colon_produces_valid_yaml(self, kb_path: Path, sample_pdf: Path):
        """Local file stub title with colons must produce valid YAML frontmatter."""
        add_source.register_source(
            str(kb_path), str(sample_pdf), source_id="tang-2010",
            title="Infrastructure: More, Better, Faster (Tang et al., 2010)",
        )
        stub = kb_path / "sources" / "files" / "tang-2010.md"
        content = stub.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        fm = yaml.safe_load(parts[1])
        assert fm["title"] == "Infrastructure: More, Better, Faster (Tang et al., 2010)"


class TestIdentifiers:
    def test_identifiers_stored_in_config(self, kb_path: Path, sample_pdf: Path):
        add_source.register_source(
            str(kb_path), str(sample_pdf), source_id="knuth-1997",
            identifiers={"isbn": "978-0-201-89683-1"},
        )
        config = yaml.safe_load(
            (kb_path / ".kb" / "config.yaml").read_text(encoding="utf-8")
        )
        assert config["sources"][0]["identifiers"] == {"isbn": "978-0-201-89683-1"}

    def test_multiple_identifiers(self, kb_path: Path, sample_pdf: Path):
        add_source.register_source(
            str(kb_path), str(sample_pdf), source_id="vaswani-2017",
            identifiers={"doi": "10.5555/3295222.3295349", "arxiv": "1706.03762"},
        )
        config = yaml.safe_load(
            (kb_path / ".kb" / "config.yaml").read_text(encoding="utf-8")
        )
        ids = config["sources"][0]["identifiers"]
        assert ids["doi"] == "10.5555/3295222.3295349"
        assert ids["arxiv"] == "1706.03762"

    def test_identifiers_in_reference_stub_frontmatter(self, kb_path: Path):
        add_source.register_source(
            str(kb_path), "https://example.com/paper",
            source_id="smith-2024", is_reference=True, title="A Paper",
            identifiers={"doi": "10.1234/example"},
        )
        stub = kb_path / "sources" / "references" / "smith-2024.md"
        content = stub.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        fm = yaml.safe_load(parts[1])
        assert fm["identifiers"] == {"doi": "10.1234/example"}

    def test_identifiers_in_file_stub_frontmatter(self, kb_path: Path, sample_pdf: Path):
        add_source.register_source(
            str(kb_path), str(sample_pdf), source_id="knuth-1997",
            identifiers={"isbn": "978-0-201-89683-1"},
        )
        stub = kb_path / "sources" / "files" / "knuth-1997.md"
        content = stub.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        fm = yaml.safe_load(parts[1])
        assert fm["identifiers"] == {"isbn": "978-0-201-89683-1"}

    def test_identifiers_in_reference_stub_body(self, kb_path: Path):
        add_source.register_source(
            str(kb_path), "https://example.com/paper",
            source_id="smith-2024", is_reference=True, title="A Paper",
            identifiers={"doi": "10.1234/example", "isbn": "978-0-13-468599-1"},
        )
        stub = kb_path / "sources" / "references" / "smith-2024.md"
        content = stub.read_text(encoding="utf-8")
        assert "**DOI**: 10.1234/example" in content
        assert "**ISBN**: 978-0-13-468599-1" in content

    def test_identifiers_in_file_stub_body(self, kb_path: Path, sample_pdf: Path):
        add_source.register_source(
            str(kb_path), str(sample_pdf), source_id="knuth-1997",
            identifiers={"isbn": "978-0-201-89683-1"},
        )
        stub = kb_path / "sources" / "files" / "knuth-1997.md"
        content = stub.read_text(encoding="utf-8")
        assert "**ISBN**: 978-0-201-89683-1" in content

    def test_no_identifiers_omits_field(self, kb_path: Path, sample_pdf: Path):
        """When no identifiers provided, config entry and stub have no identifiers key."""
        add_source.register_source(
            str(kb_path), str(sample_pdf), source_id="real-2020",
        )
        config = yaml.safe_load(
            (kb_path / ".kb" / "config.yaml").read_text(encoding="utf-8")
        )
        assert "identifiers" not in config["sources"][0]
        stub = kb_path / "sources" / "files" / "real-2020.md"
        content = stub.read_text(encoding="utf-8")
        assert "identifiers" not in content.lower().split("---", 2)[1]

    def test_identifiers_returned_in_result(self, kb_path: Path, sample_pdf: Path):
        result = add_source.register_source(
            str(kb_path), str(sample_pdf), source_id="knuth-1997",
            identifiers={"isbn": "978-0-201-89683-1"},
        )
        assert result["identifiers"] == {"isbn": "978-0-201-89683-1"}

    def test_identifiers_absent_from_result_when_empty(self, kb_path: Path, sample_pdf: Path):
        result = add_source.register_source(
            str(kb_path), str(sample_pdf), source_id="real-2020",
        )
        assert "identifiers" not in result


class TestIdentifiersCli:
    def test_identifier_cli_flag(self, kb_path: Path, sample_pdf: Path, capsys):
        add_source.main([
            "--kb-path", str(kb_path),
            "--source", str(sample_pdf),
            "--source-id", "knuth-1997",
            "--identifier", "isbn:978-0-201-89683-1",
        ])
        out = json.loads(capsys.readouterr().out)
        assert out["identifiers"] == {"isbn": "978-0-201-89683-1"}

    def test_multiple_identifier_flags(self, kb_path: Path, sample_pdf: Path, capsys):
        add_source.main([
            "--kb-path", str(kb_path),
            "--source", str(sample_pdf),
            "--source-id", "vaswani-2017",
            "--identifier", "doi:10.5555/3295222.3295349",
            "--identifier", "arxiv:1706.03762",
        ])
        out = json.loads(capsys.readouterr().out)
        assert out["identifiers"]["doi"] == "10.5555/3295222.3295349"
        assert out["identifiers"]["arxiv"] == "1706.03762"


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
