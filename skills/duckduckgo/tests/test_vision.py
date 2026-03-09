"""Tests for DuckDuckGo visual search functionality."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from contracts import ContractViolationError
from vision import find_similar_images, get_image_info


@pytest.fixture
def sample_image(tmp_path):
    """Create a minimal valid PNG for testing."""
    from PIL import Image

    img = Image.new("RGB", (100, 50), color="red")
    path = tmp_path / "test_photo.png"
    img.save(path)
    return str(path)


class TestGetImageInfoPreconditions:
    """Test image_path validation via @precondition."""

    def test_nonexistent_file_raises(self):
        with pytest.raises(ContractViolationError, match="existing file"):
            get_image_info("/nonexistent/image.png")


class TestGetImageInfo:
    """Test image metadata extraction."""

    def test_returns_correct_dimensions(self, sample_image):
        info = get_image_info(sample_image)

        assert info["width"] == 100
        assert info["height"] == 50

    def test_returns_format_and_mode(self, sample_image):
        info = get_image_info(sample_image)

        assert info["format"] == "PNG"
        assert info["mode"] == "RGB"

    def test_returns_file_size(self, sample_image):
        info = get_image_info(sample_image)

        assert info["file_size_bytes"] > 0


class TestFindSimilarImagesPreconditions:
    """Test image_path validation via @precondition."""

    def test_nonexistent_file_raises(self):
        with pytest.raises(ContractViolationError, match="existing file"):
            find_similar_images("/nonexistent/image.jpg")


class TestFindSimilarImages:
    """Test similar image search."""

    @patch("vision.search_image")
    def test_uses_filename_as_query(self, mock_search, sample_image):
        mock_search.return_value = [{"title": "Similar", "image": "https://example.com/img.jpg"}]

        results = find_similar_images(sample_image)

        # Filename is "test_photo.png", stem is "test_photo", query becomes "test photo"
        mock_search.assert_called_once_with("test photo")
        assert len(results) == 1

    @patch("vision.search_image")
    def test_handles_short_filename(self, mock_search, tmp_path):
        """If filename stem is < 2 chars, falls back to 'image' as query."""
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (10, 10))
        path = tmp_path / "x.png"
        img.save(path)

        mock_search.return_value = []

        find_similar_images(str(path))

        mock_search.assert_called_once_with("image")
