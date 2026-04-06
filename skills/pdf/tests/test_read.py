# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pytest >= 8.0",
#   "PyMuPDF >= 1.25",
#   "pymupdf4llm >= 0.0.17",
# ]
# ///
"""Tests for read.py — PDF page extraction as markdown."""

import os
import sys
import tempfile

import pymupdf
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from contracts import ContractViolationError
from read import read_pages


@pytest.fixture
def multi_page_pdf(tmp_path):
    """Create a 5-page PDF with distinct content per page."""
    path = tmp_path / "multi.pdf"
    doc = pymupdf.open()
    for i in range(1, 6):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i} Title", fontsize=20)
        page.insert_text((72, 120), f"Content on page {i}. " * 10, fontsize=12)
    doc.save(str(path))
    doc.close()
    return str(path)


class TestReadPreconditions:
    """Test input validation."""

    def test_nonexistent_file_raises(self):
        with pytest.raises(ContractViolationError, match="does not exist"):
            read_pages("/nonexistent/file.pdf")

    def test_empty_path_raises(self):
        with pytest.raises(ContractViolationError, match="must not be empty"):
            read_pages("")

    def test_invalid_page_range_raises(self, multi_page_pdf):
        with pytest.raises(ContractViolationError, match="start.*must be >= 1"):
            read_pages(multi_page_pdf, page_start=0)

    def test_end_before_start_raises(self, multi_page_pdf):
        with pytest.raises(ContractViolationError, match="end.*must be >= start"):
            read_pages(multi_page_pdf, page_start=3, page_end=1)


class TestReadOutput:
    """Test page content extraction."""

    def test_reads_all_pages_by_default(self, multi_page_pdf):
        result = read_pages(multi_page_pdf)
        assert len(result["pages"]) == 5

    def test_reads_page_range(self, multi_page_pdf):
        result = read_pages(multi_page_pdf, page_start=2, page_end=3)
        assert len(result["pages"]) == 2
        assert result["pages"][0]["number"] == 2
        assert result["pages"][1]["number"] == 3

    def test_reads_single_page(self, multi_page_pdf):
        result = read_pages(multi_page_pdf, page_start=3, page_end=3)
        assert len(result["pages"]) == 1
        assert result["pages"][0]["number"] == 3

    def test_page_has_markdown_content(self, multi_page_pdf):
        result = read_pages(multi_page_pdf, page_start=1, page_end=1)
        page = result["pages"][0]
        assert "markdown" in page
        assert "Page 1 Title" in page["markdown"]

    def test_page_has_word_count(self, multi_page_pdf):
        result = read_pages(multi_page_pdf, page_start=1, page_end=1)
        page = result["pages"][0]
        assert "word_count" in page
        assert page["word_count"] > 0

    def test_clamps_end_to_page_count(self, multi_page_pdf):
        result = read_pages(multi_page_pdf, page_start=1, page_end=999)
        assert len(result["pages"]) == 5

    def test_returns_total_page_count(self, multi_page_pdf):
        result = read_pages(multi_page_pdf, page_start=2, page_end=3)
        assert result["total_pages"] == 5
