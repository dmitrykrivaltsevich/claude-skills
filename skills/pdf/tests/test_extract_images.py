# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pytest >= 8.0",
#   "PyMuPDF >= 1.25",
# ]
# ///
"""Tests for extract_images.py — embedded image extraction from PDF."""

import os
import sys

import pymupdf
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from contracts import ContractViolationError
from extract_images import extract_images


@pytest.fixture
def pdf_with_images(tmp_path):
    """Create a PDF with embedded images."""
    path = tmp_path / "with_images.pdf"
    doc = pymupdf.open()

    # Page 1: one image
    page1 = doc.new_page()
    page1.insert_text((72, 72), "Page with image", fontsize=12)
    img1 = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 150), 0)
    img1.set_rect(img1.irect, (255, 0, 0))  # red
    page1.insert_image(pymupdf.Rect(72, 100, 272, 250), pixmap=img1)

    # Page 2: two images
    page2 = doc.new_page()
    img2 = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), 0)
    img2.set_rect(img2.irect, (0, 255, 0))  # green
    page2.insert_image(pymupdf.Rect(72, 72, 172, 172), pixmap=img2)
    img3 = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), 0)
    img3.set_rect(img3.irect, (0, 0, 255))  # blue
    page2.insert_image(pymupdf.Rect(200, 72, 300, 172), pixmap=img3)

    # Page 3: no images
    page3 = doc.new_page()
    page3.insert_text((72, 72), "Text only page", fontsize=12)

    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def pdf_no_images(tmp_path):
    """Create a PDF with no images."""
    path = tmp_path / "no_images.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Just text", fontsize=12)
    doc.save(str(path))
    doc.close()
    return str(path)


class TestExtractImagesPreconditions:
    """Test input validation."""

    def test_nonexistent_file_raises(self):
        with pytest.raises(ContractViolationError, match="does not exist"):
            extract_images("/nonexistent/file.pdf", "/tmp")

    def test_empty_path_raises(self):
        with pytest.raises(ContractViolationError, match="must not be empty"):
            extract_images("", "/tmp")


class TestExtractImagesOutput:
    """Test image extraction."""

    def test_extracts_images(self, pdf_with_images, tmp_path):
        out_dir = str(tmp_path / "output")
        result = extract_images(pdf_with_images, out_dir)
        assert len(result["images"]) >= 2

    def test_image_has_required_fields(self, pdf_with_images, tmp_path):
        out_dir = str(tmp_path / "output")
        result = extract_images(pdf_with_images, out_dir)
        img = result["images"][0]
        assert "page" in img
        assert "path" in img
        assert "width" in img
        assert "height" in img

    def test_image_files_exist_on_disk(self, pdf_with_images, tmp_path):
        out_dir = str(tmp_path / "output")
        result = extract_images(pdf_with_images, out_dir)
        for img in result["images"]:
            assert os.path.isfile(img["path"])

    def test_no_images_returns_empty(self, pdf_no_images, tmp_path):
        out_dir = str(tmp_path / "output")
        result = extract_images(pdf_no_images, out_dir)
        assert result["images"] == []

    def test_page_range_filter(self, pdf_with_images, tmp_path):
        out_dir = str(tmp_path / "output")
        result = extract_images(pdf_with_images, out_dir, page_start=1, page_end=1)
        pages = {img["page"] for img in result["images"]}
        assert 2 not in pages
