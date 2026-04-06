# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pytest >= 8.0",
#   "PyMuPDF >= 1.25",
# ]
# ///
"""Tests for render.py — render PDF pages to high-DPI PNG images.

render.py is the bridge between binary PDF and LLM vision. Two use cases:
1. OCR: scanned PDFs with no text layer → render to PNG → LLM reads via vision
2. Visual QA: after write.py produces a PDF, render a page to verify appearance
"""

import os
import sys

import pymupdf
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from contracts import ContractViolationError
from render import render_pages


@pytest.fixture
def sample_pdf(tmp_path):
    """Create a simple PDF for rendering tests."""
    path = tmp_path / "render_test.pdf"
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1}", fontsize=24)
    doc.save(str(path))
    doc.close()
    return str(path)


class TestRenderPreconditions:
    """Test input validation."""

    def test_nonexistent_file_raises(self):
        with pytest.raises(ContractViolationError, match="does not exist"):
            render_pages("/nonexistent/file.pdf", "/tmp")

    def test_empty_path_raises(self):
        with pytest.raises(ContractViolationError, match="must not be empty"):
            render_pages("", "/tmp")

    def test_invalid_dpi_raises(self, sample_pdf):
        with pytest.raises(ContractViolationError, match="DPI must be"):
            render_pages(sample_pdf, "/tmp", dpi=0)


class TestRenderOutput:
    """Test page rendering."""

    def test_renders_all_pages_by_default(self, sample_pdf, tmp_path):
        out_dir = str(tmp_path / "rendered")
        result = render_pages(sample_pdf, out_dir)
        assert len(result["pages"]) == 3

    def test_renders_page_range(self, sample_pdf, tmp_path):
        out_dir = str(tmp_path / "rendered")
        result = render_pages(sample_pdf, out_dir, page_start=2, page_end=2)
        assert len(result["pages"]) == 1
        assert result["pages"][0]["number"] == 2

    def test_output_files_exist(self, sample_pdf, tmp_path):
        out_dir = str(tmp_path / "rendered")
        result = render_pages(sample_pdf, out_dir)
        for page in result["pages"]:
            assert os.path.isfile(page["path"])

    def test_default_dpi_is_400(self, sample_pdf, tmp_path):
        out_dir = str(tmp_path / "rendered")
        result = render_pages(sample_pdf, out_dir)
        assert result["dpi"] == 400

    def test_custom_dpi(self, sample_pdf, tmp_path):
        out_dir = str(tmp_path / "rendered")
        result = render_pages(sample_pdf, out_dir, dpi=150)
        assert result["dpi"] == 150

    def test_high_dpi_produces_large_images(self, sample_pdf, tmp_path):
        out_dir = str(tmp_path / "rendered")
        result = render_pages(sample_pdf, out_dir, dpi=400)
        page = result["pages"][0]
        # A4 at 400 DPI ≈ 3307×4677 pixels
        assert page["width"] > 3000
        assert page["height"] > 4000

    def test_page_has_required_fields(self, sample_pdf, tmp_path):
        out_dir = str(tmp_path / "rendered")
        result = render_pages(sample_pdf, out_dir)
        page = result["pages"][0]
        assert "number" in page
        assert "path" in page
        assert "width" in page
        assert "height" in page
        assert "file_size_bytes" in page
