# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pytest >= 8.0",
#   "typst >= 0.12",
# ]
# ///
"""Tests for write.py — compile Typst source to PDF."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from contracts import ContractViolationError
from write import compile_pdf


@pytest.fixture
def simple_typst(tmp_path):
    """Create a simple Typst source file."""
    path = tmp_path / "test.typ"
    path.write_text(
        '#set page(paper: "a4")\n'
        '#set text(size: 12pt)\n'
        "= Hello World\n"
        "This is a test document.\n"
    )
    return str(path)


@pytest.fixture
def typst_with_math(tmp_path):
    """Create a Typst file with math content."""
    path = tmp_path / "math.typ"
    path.write_text(
        '#set page(paper: "a4")\n'
        "= Mathematics\n"
        "The quadratic formula: $ x = (-b plus.minus sqrt(b^2 - 4a c)) / (2a) $\n"
    )
    return str(path)


@pytest.fixture
def invalid_typst(tmp_path):
    """Create a Typst file with syntax errors."""
    path = tmp_path / "invalid.typ"
    path.write_text("#set page(paper: )\n= Broken\n")
    return str(path)


class TestWritePreconditions:
    """Test input validation."""

    def test_nonexistent_source_raises(self):
        with pytest.raises(ContractViolationError, match="does not exist"):
            compile_pdf("/nonexistent/file.typ", "/tmp/out.pdf")

    def test_empty_source_path_raises(self):
        with pytest.raises(ContractViolationError, match="must not be empty"):
            compile_pdf("", "/tmp/out.pdf")

    def test_empty_output_path_raises(self, simple_typst):
        with pytest.raises(ContractViolationError, match="must not be empty"):
            compile_pdf(simple_typst, "")


class TestWriteOutput:
    """Test PDF compilation."""

    def test_produces_pdf_file(self, simple_typst, tmp_path):
        out = str(tmp_path / "output.pdf")
        result = compile_pdf(simple_typst, out)
        assert os.path.isfile(out)
        assert result["pdf_path"] == out

    def test_returns_page_count(self, simple_typst, tmp_path):
        out = str(tmp_path / "output.pdf")
        result = compile_pdf(simple_typst, out)
        assert result["page_count"] >= 1

    def test_returns_file_size(self, simple_typst, tmp_path):
        out = str(tmp_path / "output.pdf")
        result = compile_pdf(simple_typst, out)
        assert result["file_size_bytes"] > 0

    def test_compiles_math(self, typst_with_math, tmp_path):
        out = str(tmp_path / "math_output.pdf")
        result = compile_pdf(typst_with_math, out)
        assert os.path.isfile(out)

    def test_invalid_source_returns_errors(self, invalid_typst, tmp_path):
        out = str(tmp_path / "output.pdf")
        result = compile_pdf(invalid_typst, out)
        assert len(result["errors"]) > 0
        assert result["success"] is False

    def test_returns_warnings(self, simple_typst, tmp_path):
        out = str(tmp_path / "output.pdf")
        result = compile_pdf(simple_typst, out)
        assert "warnings" in result

    def test_success_flag_on_valid_source(self, simple_typst, tmp_path):
        out = str(tmp_path / "output.pdf")
        result = compile_pdf(simple_typst, out)
        assert result["success"] is True
