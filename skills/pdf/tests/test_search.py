# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pytest >= 8.0",
#   "PyMuPDF >= 1.25",
# ]
# ///
"""Tests for search.py — full-text search within PDF."""

import os
import sys

import pymupdf
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from contracts import ContractViolationError
from search import search_pdf


@pytest.fixture
def searchable_pdf(tmp_path):
    """Create a PDF with known searchable content across pages."""
    path = tmp_path / "searchable.pdf"
    doc = pymupdf.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "The quick brown fox jumps over the lazy dog.", fontsize=12)
    page1.insert_text((72, 100), "Python is a programming language.", fontsize=12)

    page2 = doc.new_page()
    page2.insert_text((72, 72), "The fox returned to the forest.", fontsize=12)
    page2.insert_text((72, 100), "Java is also a programming language.", fontsize=12)

    page3 = doc.new_page()
    page3.insert_text((72, 72), "Nothing relevant here about animals.", fontsize=12)

    doc.save(str(path))
    doc.close()
    return str(path)


class TestSearchPreconditions:
    """Test input validation."""

    def test_nonexistent_file_raises(self):
        with pytest.raises(ContractViolationError, match="does not exist"):
            search_pdf("/nonexistent/file.pdf", "test")

    def test_empty_query_raises(self, searchable_pdf):
        with pytest.raises(ContractViolationError, match="must not be empty"):
            search_pdf(searchable_pdf, "")

    def test_empty_path_raises(self):
        with pytest.raises(ContractViolationError, match="must not be empty"):
            search_pdf("", "test")


class TestSearchOutput:
    """Test search result structure and content."""

    def test_finds_matches_on_correct_pages(self, searchable_pdf):
        result = search_pdf(searchable_pdf, "fox")
        assert len(result["matches"]) == 2
        pages = [m["page"] for m in result["matches"]]
        assert 1 in pages
        assert 2 in pages

    def test_match_includes_context(self, searchable_pdf):
        result = search_pdf(searchable_pdf, "fox")
        for match in result["matches"]:
            assert "context" in match
            assert len(match["context"]) > 0

    def test_no_matches_returns_empty(self, searchable_pdf):
        result = search_pdf(searchable_pdf, "elephant")
        assert result["matches"] == []

    def test_returns_query_in_output(self, searchable_pdf):
        result = search_pdf(searchable_pdf, "fox")
        assert result["query"] == "fox"

    def test_returns_total_match_count(self, searchable_pdf):
        result = search_pdf(searchable_pdf, "programming")
        assert result["total_matches"] == 2

    def test_search_specific_page_range(self, searchable_pdf):
        result = search_pdf(searchable_pdf, "fox", page_start=2, page_end=2)
        assert len(result["matches"]) == 1
        assert result["matches"][0]["page"] == 2
