# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pytest >= 8.0",
#   "PyMuPDF >= 1.25",
# ]
# ///
"""Tests for info.py — PDF metadata and structural analysis."""

import json
import os
import sys
import tempfile

import pymupdf
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from contracts import ContractViolationError
from info import get_info


@pytest.fixture
def text_pdf(tmp_path):
    """Create a simple text PDF for testing."""
    path = tmp_path / "text.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Chapter 1: Introduction", fontsize=20)
    page.insert_text((72, 120), "This is a test paragraph.", fontsize=12)
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Chapter 2: Details", fontsize=20)
    page2.insert_text((72, 120), "More content here.", fontsize=12)
    doc.set_metadata({"title": "Test Document", "author": "Test Author"})
    doc.set_toc([[1, "Chapter 1: Introduction", 1], [1, "Chapter 2: Details", 2]])
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def image_only_pdf(tmp_path):
    """Create a PDF with only an image (no text layer) — simulates scanned page."""
    path = tmp_path / "image_only.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    # Create a small image and insert it
    img = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), 0)
    img.set_rect(img.irect, (255, 0, 0))  # red square
    page.insert_image(page.rect, pixmap=img)
    doc.save(str(path))
    doc.close()
    return str(path)


class TestInfoPreconditions:
    """Test input validation."""

    def test_nonexistent_file_raises(self):
        with pytest.raises(ContractViolationError, match="does not exist"):
            get_info("/nonexistent/file.pdf")

    def test_empty_path_raises(self):
        with pytest.raises(ContractViolationError, match="must not be empty"):
            get_info("")


class TestInfoOutput:
    """Test metadata extraction."""

    def test_returns_page_count(self, text_pdf):
        result = get_info(text_pdf)
        assert result["page_count"] == 2

    def test_returns_metadata(self, text_pdf):
        result = get_info(text_pdf)
        assert result["title"] == "Test Document"
        assert result["author"] == "Test Author"

    def test_returns_toc(self, text_pdf):
        result = get_info(text_pdf)
        assert len(result["toc"]) == 2
        assert result["toc"][0]["title"] == "Chapter 1: Introduction"
        assert result["toc"][0]["page"] == 1
        assert result["toc"][0]["level"] == 1

    def test_returns_page_analysis(self, text_pdf):
        result = get_info(text_pdf)
        assert len(result["pages"]) == 2
        for page in result["pages"]:
            assert "number" in page
            assert "has_text" in page
            assert "has_images" in page
            assert "width" in page
            assert "height" in page

    def test_text_pdf_pages_have_text(self, text_pdf):
        result = get_info(text_pdf)
        assert result["pages"][0]["has_text"] is True

    def test_image_only_pdf_detected(self, image_only_pdf):
        result = get_info(image_only_pdf)
        assert result["pages"][0]["has_images"] is True

    def test_returns_file_size(self, text_pdf):
        result = get_info(text_pdf)
        assert result["file_size_bytes"] > 0

    def test_output_is_json_serializable(self, text_pdf):
        result = get_info(text_pdf)
        json.dumps(result)  # should not raise
