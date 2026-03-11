"""Tests for download.py — URL fetcher and converter."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from download import (
    _extract_readable,
    _html_to_markdown,
    _slug_from_url,
    infer_format,
    save_md,
    save_txt,
)


class TestSlugFromUrl:
    """Test URL-to-filename conversion."""

    def test_simple_path(self):
        assert _slug_from_url("https://example.com/article-title") == "article-title"

    def test_trailing_slash_stripped(self):
        assert _slug_from_url("https://example.com/page/") == "page"

    def test_root_path_becomes_index(self):
        result = _slug_from_url("https://example.com/")
        # stem of "index" or derived from root — should not be empty
        assert result

    def test_special_chars_replaced(self):
        slug = _slug_from_url("https://example.com/my page (1)")
        assert " " not in slug
        assert "(" not in slug

    def test_long_path_truncated(self):
        long_path = "a" * 200
        slug = _slug_from_url(f"https://example.com/{long_path}")
        assert len(slug) <= 80

    def test_nested_path_uses_last_segment(self):
        slug = _slug_from_url("https://example.com/blog/2026/my-article.html")
        assert slug == "my-article"


class TestInferFormat:
    """Test output format inference."""

    def test_explicit_format_wins(self):
        assert infer_format(Path("out.txt"), "pdf") == "pdf"

    def test_infer_from_extension_txt(self):
        assert infer_format(Path("out.txt"), None) == "txt"

    def test_infer_from_extension_md(self):
        assert infer_format(Path("out.md"), None) == "md"

    def test_infer_from_extension_pdf(self):
        assert infer_format(Path("out.pdf"), None) == "pdf"

    def test_unknown_extension_defaults_txt(self):
        assert infer_format(Path("out.xyz"), None) == "txt"

    def test_no_output_no_format_defaults_txt(self):
        assert infer_format(None, None) == "txt"

    def test_uppercase_format_normalized(self):
        assert infer_format(None, "PDF") == "pdf"


class TestExtractReadable:
    """Test HTML-to-text extraction."""

    def test_extracts_title(self):
        html = "<html><head><title>My Title</title></head><body>Content</body></html>"
        title, text = _extract_readable(html)
        assert title == "My Title"

    def test_extracts_body_text(self):
        html = "<html><body><p>Hello world</p></body></html>"
        _, text = _extract_readable(html)
        assert "Hello world" in text

    def test_removes_scripts(self):
        html = "<body><script>alert('xss')</script><p>Content</p></body>"
        _, text = _extract_readable(html)
        assert "alert" not in text

    def test_removes_nav_footer(self):
        html = "<body><nav>Menu</nav><p>Article</p><footer>Footer</footer></body>"
        _, text = _extract_readable(html)
        assert "Menu" not in text
        assert "Footer" not in text
        assert "Article" in text

    def test_prefers_article_tag(self):
        html = "<body><div>Sidebar</div><article><p>Main content</p></article></body>"
        _, text = _extract_readable(html)
        assert "Main content" in text

    def test_collapses_blank_lines(self):
        html = "<body><p>A</p><br><br><br><br><br><p>B</p></body>"
        _, text = _extract_readable(html)
        assert "\n\n\n" not in text

    def test_no_title_returns_empty(self):
        html = "<body><p>Content</p></body>"
        title, _ = _extract_readable(html)
        assert title == ""

    def test_removes_style_tags(self):
        html = "<body><style>.red{color:red}</style><p>Visible</p></body>"
        _, text = _extract_readable(html)
        assert "red" not in text
        assert "Visible" in text


class TestHtmlToMarkdown:
    """Test HTML-to-Markdown conversion."""

    def test_extracts_title(self):
        html = "<html><head><title>Title</title></head><body><p>Text</p></body></html>"
        title, _ = _html_to_markdown(html)
        assert title == "Title"

    def test_preserves_links(self):
        html = '<body><a href="https://example.com">Link</a></body>'
        _, md = _html_to_markdown(html)
        assert "https://example.com" in md
        assert "Link" in md

    def test_removes_scripts(self):
        html = "<body><script>evil()</script><p>Safe</p></body>"
        _, md = _html_to_markdown(html)
        assert "evil" not in md
        assert "Safe" in md

    def test_no_title_returns_empty(self):
        html = "<body><p>Just text</p></body>"
        title, _ = _html_to_markdown(html)
        assert title == ""


class TestSaveTxt:
    """Test text file saving."""

    def test_saves_with_title(self, tmp_path):
        html = "<html><head><title>Test</title></head><body><p>Hello</p></body></html>"
        dest = tmp_path / "out.txt"
        save_txt(html, dest)
        content = dest.read_text()
        assert "Test" in content
        assert "Hello" in content

    def test_saves_without_title(self, tmp_path):
        html = "<body><p>No title here</p></body>"
        dest = tmp_path / "out.txt"
        save_txt(html, dest)
        content = dest.read_text()
        assert "No title here" in content

    def test_title_underline_present(self, tmp_path):
        html = "<html><head><title>My Title</title></head><body><p>Body</p></body></html>"
        dest = tmp_path / "out.txt"
        save_txt(html, dest)
        content = dest.read_text()
        assert "=====" in content


class TestSaveMd:
    """Test markdown file saving."""

    def test_saves_with_title_heading(self, tmp_path):
        html = "<html><head><title>Article</title></head><body><p>Body</p></body></html>"
        dest = tmp_path / "out.md"
        save_md(html, dest)
        content = dest.read_text()
        assert content.startswith("# Article")

    def test_saves_without_title(self, tmp_path):
        html = "<body><p>Body only</p></body>"
        dest = tmp_path / "out.md"
        save_md(html, dest)
        content = dest.read_text()
        assert "Body only" in content
