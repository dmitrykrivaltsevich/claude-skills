"""Tests for DuckDuckGo visual search functionality."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from contracts import ContractViolationError
from vision import (
    _build_query_from_image,
    _extract_image_metadata,
    find_similar_images,
    get_image_info,
)


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


class TestExtractImageMetadata:
    """Test rich metadata extraction from images."""

    def test_extracts_dimensions(self, sample_image):
        metadata = _extract_image_metadata(sample_image)

        assert metadata["width"] == 100
        assert metadata["height"] == 50

    def test_extracts_format(self, sample_image):
        metadata = _extract_image_metadata(sample_image)

        assert metadata["format"] == "PNG"

    def test_handles_no_exif(self, sample_image):
        """PNG without EXIF should still return basic metadata."""
        metadata = _extract_image_metadata(sample_image)

        assert "width" in metadata
        assert "image_description" not in metadata


class TestBuildQueryFromImage:
    """Test search query construction from image metadata."""

    def test_uses_exif_description(self):
        query = _build_query_from_image(
            "/tmp/photo.jpg",
            {"image_description": "Sunset over ocean"},
        )
        assert query == "Sunset over ocean"

    def test_uses_xp_subject(self):
        query = _build_query_from_image(
            "/tmp/photo.jpg",
            {"xp_subject": "beach vacation"},
        )
        assert query == "beach vacation"

    def test_uses_xp_keywords_when_no_description(self):
        query = _build_query_from_image(
            "/tmp/photo.jpg",
            {"xp_keywords": "nature; mountains; hiking"},
        )
        assert query == "nature; mountains; hiking"

    def test_prefers_description_over_keywords(self):
        query = _build_query_from_image(
            "/tmp/photo.jpg",
            {
                "image_description": "A red fox in winter",
                "xp_keywords": "animals; wildlife",
            },
        )
        assert query == "A red fox in winter"

    def test_strips_camera_prefix_IMG(self):
        query = _build_query_from_image("/tmp/IMG_beach_view.jpg", {})
        assert "IMG" not in query
        assert "beach view" in query

    def test_strips_camera_prefix_DSC(self):
        query = _build_query_from_image("/tmp/DSC_sunset_harbor.jpg", {})
        assert "DSC" not in query
        assert "sunset harbor" in query

    def test_strips_camera_prefix_Screenshot(self):
        query = _build_query_from_image("/tmp/Screenshot_code_editor.jpg", {})
        assert "Screenshot" not in query.lower()
        assert "code editor" in query

    def test_rejects_pure_timestamp_filenames(self):
        query = _build_query_from_image("/tmp/20260310_143022.jpg", {})
        assert query == ""

    def test_rejects_camera_prefix_with_timestamp(self):
        query = _build_query_from_image("/tmp/IMG_20260310_143022.jpg", {})
        assert query == ""

    def test_rejects_pure_numbers(self):
        query = _build_query_from_image("/tmp/12345678.jpg", {})
        assert query == ""

    def test_uses_meaningful_filename(self):
        query = _build_query_from_image("/tmp/golden_retriever_puppy.jpg", {})
        assert "golden retriever puppy" in query

    def test_truncates_long_metadata(self):
        query = _build_query_from_image(
            "/tmp/photo.jpg",
            {"image_description": "x" * 500},
        )
        assert len(query) <= 200

    def test_short_exif_ignored(self):
        """EXIF values shorter than 3 chars are not useful."""
        query = _build_query_from_image(
            "/tmp/nice_landscape.jpg",
            {"image_description": "OK"},
        )
        # Falls through to filename
        assert "nice landscape" in query


class TestFindSimilarImagesPreconditions:
    """Test image_path validation via @precondition."""

    def test_nonexistent_file_raises(self):
        with pytest.raises(ContractViolationError, match="existing file"):
            find_similar_images("/nonexistent/image.jpg")


class TestFindSimilarImages:
    """Test similar image search with metadata awareness."""

    @patch("vision.search_image")
    def test_returns_structured_result(self, mock_search, sample_image):
        mock_search.return_value = [
            {"title": "Similar", "image": "https://example.com/img.jpg"}
        ]

        result = find_similar_images(sample_image)

        assert "image_metadata" in result
        assert "query_used" in result
        assert "results" in result

    @patch("vision.search_image")
    def test_uses_meaningful_filename_as_query(self, mock_search, sample_image):
        mock_search.return_value = []

        result = find_similar_images(sample_image)

        # sample_image name is "test_photo.png" → query "test photo"
        assert result["query_used"] == "test photo"
        mock_search.assert_called_once_with("test photo")

    @patch("vision._extract_image_metadata")
    @patch("vision.search_image")
    def test_returns_diagnostic_when_no_query(self, mock_search, mock_meta, tmp_path):
        """Unhelpful filenames with no EXIF get a diagnostic instead of bad search."""
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (10, 10))
        path = tmp_path / "IMG_20260310_143022.jpg"
        img.save(path)

        mock_meta.return_value = {}

        result = find_similar_images(str(path))

        assert "diagnostic" in result
        assert result["results"] == []
        mock_search.assert_not_called()

    @patch("vision._extract_image_metadata")
    @patch("vision.search_image")
    def test_uses_exif_over_filename(self, mock_search, mock_meta, sample_image):
        mock_meta.return_value = {"image_description": "Red panda eating bamboo"}
        mock_search.return_value = [{"title": "Match"}]

        result = find_similar_images(sample_image)

        assert result["query_used"] == "Red panda eating bamboo"
        mock_search.assert_called_once_with("Red panda eating bamboo")

    @patch("vision.search_image")
    def test_includes_metadata_in_result(self, mock_search, sample_image):
        mock_search.return_value = []

        result = find_similar_images(sample_image)

        assert result["image_metadata"]["width"] == 100
        assert result["image_metadata"]["height"] == 50
