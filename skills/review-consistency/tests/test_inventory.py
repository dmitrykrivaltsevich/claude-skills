"""Tests for inventory.py — file enumeration with hashing for review coverage."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import inventory
from contracts import ContractViolationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_tree(tmp_path: Path) -> Path:
    """Create a sample directory tree for testing."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')\n")
    (tmp_path / "src" / "utils.py").write_text("def add(a, b): return a + b\n")
    (tmp_path / "src" / "__pycache__").mkdir()
    (tmp_path / "src" / "__pycache__" / "main.cpython-311.pyc").write_bytes(b"\x00")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("# Docs\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]\n")
    (tmp_path / "config.yaml").write_text("key: value\n")
    return tmp_path


# ---------------------------------------------------------------------------
# scan_paths tests
# ---------------------------------------------------------------------------


class TestScanPaths:
    def test_single_file(self, tmp_path: Path):
        f = tmp_path / "hello.py"
        f.write_text("x = 1\n")
        result = inventory.scan_paths([str(f)])
        assert len(result) == 1
        assert result[0]["path"] == str(f)
        assert result[0]["size"] == len("x = 1\n")
        assert result[0]["hash"].startswith("sha256:")
        assert len(result[0]["hash"]) == 7 + 64  # "sha256:" + 64 hex chars

    def test_directory_recursive(self, sample_tree: Path):
        result = inventory.scan_paths([str(sample_tree / "src")])
        paths = {r["path"] for r in result}
        assert str(sample_tree / "src" / "main.py") in paths
        assert str(sample_tree / "src" / "utils.py") in paths

    def test_default_excludes(self, sample_tree: Path):
        """Default excludes should skip .git and __pycache__."""
        result = inventory.scan_paths([str(sample_tree)])
        paths = {r["path"] for r in result}
        assert not any("__pycache__" in p for p in paths)
        assert not any(".git" in p for p in paths)

    def test_glob_exclude_pattern(self, tmp_path: Path):
        """Glob patterns like *.egg-info should match real directory names."""
        (tmp_path / "mypackage.egg-info").mkdir()
        (tmp_path / "mypackage.egg-info" / "PKG-INFO").write_text("Name: mypackage\n")
        (tmp_path / "keep.py").write_text("x = 1\n")
        result = inventory.scan_paths([str(tmp_path)])
        paths = {r["path"] for r in result}
        assert not any(".egg-info" in p for p in paths)
        assert str(tmp_path / "keep.py") in paths

    def test_custom_excludes(self, sample_tree: Path):
        result = inventory.scan_paths(
            [str(sample_tree)],
            exclude_patterns=["docs"],
        )
        paths = {r["path"] for r in result}
        assert not any("docs" in p for p in paths)
        # src files should still be present
        assert str(sample_tree / "src" / "main.py") in paths

    def test_extension_filter(self, sample_tree: Path):
        result = inventory.scan_paths(
            [str(sample_tree)],
            extensions=[".py"],
        )
        paths = {r["path"] for r in result}
        assert all(p.endswith(".py") for p in paths)
        assert str(sample_tree / "src" / "main.py") in paths
        assert str(sample_tree / "docs" / "README.md") not in paths

    def test_multiple_paths(self, sample_tree: Path):
        result = inventory.scan_paths([
            str(sample_tree / "src" / "main.py"),
            str(sample_tree / "docs"),
        ])
        paths = {r["path"] for r in result}
        assert str(sample_tree / "src" / "main.py") in paths
        assert str(sample_tree / "docs" / "README.md") in paths
        # utils.py should NOT be included (only main.py from src)
        assert str(sample_tree / "src" / "utils.py") not in paths

    def test_empty_directory(self, tmp_path: Path):
        empty = tmp_path / "empty"
        empty.mkdir()
        result = inventory.scan_paths([str(empty)])
        assert result == []

    def test_nonexistent_path_error(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            inventory.scan_paths([str(tmp_path / "nonexistent")])

    def test_rejects_empty_paths(self):
        with pytest.raises(ContractViolationError, match="(?i)path"):
            inventory.scan_paths([])

    def test_hash_deterministic(self, tmp_path: Path):
        f = tmp_path / "test.txt"
        f.write_text("deterministic content\n")
        r1 = inventory.scan_paths([str(f)])
        r2 = inventory.scan_paths([str(f)])
        assert r1[0]["hash"] == r2[0]["hash"]

    def test_hash_changes_with_content(self, tmp_path: Path):
        f = tmp_path / "test.txt"
        f.write_text("version 1\n")
        r1 = inventory.scan_paths([str(f)])
        f.write_text("version 2\n")
        r2 = inventory.scan_paths([str(f)])
        assert r1[0]["hash"] != r2[0]["hash"]

    def test_sorted_output(self, sample_tree: Path):
        result = inventory.scan_paths([str(sample_tree)])
        paths = [r["path"] for r in result]
        assert paths == sorted(paths)


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLI:
    def test_cli_output_is_json(self, sample_tree: Path, capsys):
        inventory.main([str(sample_tree / "src" / "main.py")])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 1

    def test_cli_exclude_flag(self, sample_tree: Path, capsys):
        inventory.main([str(sample_tree), "--exclude", "docs", "src"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        paths = {d["path"] for d in data}
        assert not any("docs" in p for p in paths)
        assert not any("src" in p for p in paths)

    def test_cli_extensions_flag(self, sample_tree: Path, capsys):
        inventory.main([str(sample_tree), "--ext", ".md"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert all(d["path"].endswith(".md") for d in data)
