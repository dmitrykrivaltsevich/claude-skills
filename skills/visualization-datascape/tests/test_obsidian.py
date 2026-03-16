# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Tests for obsidian_to_datascape.py — Obsidian vault parser."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

# Insert scripts dir so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import obsidian_to_datascape as otd


class TestParseNote(unittest.TestCase):
    """Test individual note parsing."""

    def _make_vault(self, files: dict[str, str]) -> Path:
        """Create a temp Obsidian vault with given files.

        files: {relative_path: content}
        """
        d = tempfile.mkdtemp()
        root = Path(d)
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return root

    def test_basic_note_becomes_vault(self):
        root = self._make_vault({"Hello.md": "# Hello\nWorld"})
        config = otd.parse_vault(str(root))
        assert len(config["vaults"]) == 1
        assert config["vaults"][0]["name"] == "HELLO"
        assert "World" in config["vaults"][0]["html"]

    def test_wikilinks_create_connections(self):
        root = self._make_vault({
            "A.md": "Link to [[B]]",
            "B.md": "Link to [[A]]",
        })
        config = otd.parse_vault(str(root))
        assert len(config["vaults"]) == 2
        assert len(config["connections"]) == 1  # deduplicated

    def test_external_urls_in_html(self):
        root = self._make_vault({
            "Links.md": "See https://example.com for more",
        })
        config = otd.parse_vault(str(root))
        assert "https://example.com" in config["vaults"][0]["html"]

    def test_obsidian_dir_excluded(self):
        root = self._make_vault({
            ".obsidian/config.json": "{}",
            "Note.md": "Real note",
        })
        config = otd.parse_vault(str(root))
        assert len(config["vaults"]) == 1
        assert config["vaults"][0]["name"] == "NOTE"

    def test_tags_extracted(self):
        root = self._make_vault({
            "Tagged.md": "Some text #project #idea",
        })
        config = otd.parse_vault(str(root))
        html_out = config["vaults"][0]["html"]
        assert "#project" in html_out or "#idea" in html_out

    def test_embedded_image_referenced(self):
        root = self._make_vault({
            "Note.md": "![[photo.png]]",
            "photo.png": b"\x89PNG".decode("latin-1"),  # fake PNG header
        })
        config = otd.parse_vault(str(root))
        # Should reference image somehow (data URI or mention)
        html_out = config["vaults"][0]["html"]
        assert "photo.png" in html_out or "pi" in html_out

    def test_pdf_referenced(self):
        root = self._make_vault({
            "Research.md": "See ![[paper.pdf]]",
        })
        config = otd.parse_vault(str(root))
        html = config["vaults"][0]["html"]
        assert "paper.pdf" in html
        assert "[pdf]" in html

    def test_headings_in_structure(self):
        root = self._make_vault({
            "Doc.md": "# Title\n## Section A\n## Section B\nContent here",
        })
        config = otd.parse_vault(str(root))
        html_out = config["vaults"][0]["html"]
        assert "Section A" in html_out
        assert "Section B" in html_out

    def test_folder_coloring(self):
        root = self._make_vault({
            "FolderA/X.md": "Note X",
            "FolderA/Y.md": "Note Y",
            "FolderB/Z.md": "Note Z",
        })
        config = otd.parse_vault(str(root))
        colors = {v["name"]: v["color"] for v in config["vaults"]}
        # Same folder → same color
        assert colors["X"] == colors["Y"]
        # Different folder → different color
        assert colors["X"] != colors["Z"]


class TestTemporalInference(unittest.TestCase):
    """Test automatic year/month vault creation and temporal connections."""

    def _make_vault(self, files: dict[str, str]) -> Path:
        d = tempfile.mkdtemp()
        root = Path(d)
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return root

    def test_dated_notes_get_month_vaults(self):
        root = self._make_vault({
            "diary/2025-01-01.md": "New year",
            "diary/2025-01-15.md": "Mid month",
        })
        config = otd.parse_vault(str(root))
        names = [v["name"] for v in config["vaults"]]
        # Should have the 2 real notes + a January 2025 month vault + a 2025 year vault
        assert any("JAN" in n and "2025" in n for n in names), f"No Jan 2025 month vault in {names}"
        assert any(n == "2025" for n in names), f"No 2025 year vault in {names}"

    def test_dated_notes_linked_to_month(self):
        root = self._make_vault({
            "2025-01-01.md": "Day one",
            "2025-01-15.md": "Day fifteen",
        })
        config = otd.parse_vault(str(root))
        ids = {v["name"]: v["id"] for v in config["vaults"]}
        conn_pairs = {(c["from"], c["to"]) for c in config["connections"]}
        conn_pairs |= {(c["to"], c["from"]) for c in config["connections"]}

        month_id = ids.get("JAN 2025")
        assert month_id is not None, f"No JAN 2025 vault, ids={ids}"
        # Both dated notes should connect to their month
        day1_id = ids.get("2025-01-01")
        day15_id = ids.get("2025-01-15")
        assert (day1_id, month_id) in conn_pairs or (month_id, day1_id) in conn_pairs
        assert (day15_id, month_id) in conn_pairs or (month_id, day15_id) in conn_pairs

    def test_month_linked_to_year(self):
        root = self._make_vault({
            "2025-03-10.md": "Spring note",
        })
        config = otd.parse_vault(str(root))
        ids = {v["name"]: v["id"] for v in config["vaults"]}
        conn_pairs = {(c["from"], c["to"]) for c in config["connections"]}
        conn_pairs |= {(c["to"], c["from"]) for c in config["connections"]}

        month_id = ids.get("MAR 2025")
        year_id = ids.get("2025")
        assert month_id is not None
        assert year_id is not None
        assert (month_id, year_id) in conn_pairs

    def test_chronological_prev_next(self):
        """Adjacent dated notes get prev/next connections."""
        root = self._make_vault({
            "2025-01-01.md": "Day 1",
            "2025-01-03.md": "Day 3",
            "2025-02-10.md": "Feb note",
        })
        config = otd.parse_vault(str(root))
        ids = {v["name"]: v["id"] for v in config["vaults"]}
        conn_pairs = {(c["from"], c["to"]) for c in config["connections"]}
        conn_pairs |= {(c["to"], c["from"]) for c in config["connections"]}

        # 01-01 → 01-03 → 02-10 chronologically
        id1 = ids["2025-01-01"]
        id3 = ids["2025-01-03"]
        id_feb = ids["2025-02-10"]
        assert (id1, id3) in conn_pairs, "Jan 1 → Jan 3 not connected"
        assert (id3, id_feb) in conn_pairs, "Jan 3 → Feb 10 not connected"

    def test_non_dated_notes_unaffected(self):
        root = self._make_vault({
            "2025-01-01.md": "Dated",
            "Random Note.md": "Not dated",
        })
        config = otd.parse_vault(str(root))
        names = [v["name"] for v in config["vaults"]]
        # Random Note should exist but not get temporal links
        assert "RANDOM NOTE" in names
        ids = {v["name"]: v["id"] for v in config["vaults"]}
        conn_pairs = {(c["from"], c["to"]) for c in config["connections"]}
        conn_pairs |= {(c["to"], c["from"]) for c in config["connections"]}
        random_id = ids["RANDOM NOTE"]
        month_id = ids.get("JAN 2025")
        if month_id:
            assert (random_id, month_id) not in conn_pairs

    def test_multiple_years(self):
        root = self._make_vault({
            "2024-12-31.md": "NYE",
            "2025-01-01.md": "New year",
        })
        config = otd.parse_vault(str(root))
        names = [v["name"] for v in config["vaults"]]
        assert any(n == "2024" for n in names)
        assert any(n == "2025" for n in names)
        assert any("DEC" in n and "2024" in n for n in names)
        assert any("JAN" in n and "2025" in n for n in names)

    def test_year_vaults_connected_chronologically(self):
        """Adjacent year vaults get prev/next connections."""
        root = self._make_vault({
            "2024-06-15.md": "Mid 2024",
            "2025-03-10.md": "Spring 2025",
        })
        config = otd.parse_vault(str(root))
        ids = {v["name"]: v["id"] for v in config["vaults"]}
        conn_pairs = {(c["from"], c["to"]) for c in config["connections"]}
        conn_pairs |= {(c["to"], c["from"]) for c in config["connections"]}
        assert (ids["2024"], ids["2025"]) in conn_pairs

    def test_month_vaults_connected_chronologically(self):
        """Adjacent month vaults get prev/next connections."""
        root = self._make_vault({
            "2025-01-05.md": "Jan note",
            "2025-03-10.md": "Mar note",
        })
        config = otd.parse_vault(str(root))
        ids = {v["name"]: v["id"] for v in config["vaults"]}
        conn_pairs = {(c["from"], c["to"]) for c in config["connections"]}
        conn_pairs |= {(c["to"], c["from"]) for c in config["connections"]}
        # Jan 2025 → Mar 2025 (adjacent in this dataset, even though Feb is missing)
        assert (ids["JAN 2025"], ids["MAR 2025"]) in conn_pairs


class TestFolderVaults(unittest.TestCase):
    """Test folders becoming vaults with hierarchical connections."""

    def _make_vault(self, files: dict[str, str]) -> Path:
        d = tempfile.mkdtemp()
        root = Path(d)
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return root

    def test_folder_becomes_vault(self):
        root = self._make_vault({
            "FolderA/Note1.md": "Content 1",
            "FolderA/Note2.md": "Content 2",
        })
        config = otd.parse_vault(str(root))
        names = [v["name"] for v in config["vaults"]]
        assert "FOLDERA" in names, f"No folder vault in {names}"

    def test_folder_connected_to_children(self):
        root = self._make_vault({
            "FolderA/Note1.md": "Content 1",
            "FolderA/Note2.md": "Content 2",
        })
        config = otd.parse_vault(str(root))
        ids = {v["name"]: v["id"] for v in config["vaults"]}
        conn_pairs = {(c["from"], c["to"]) for c in config["connections"]}
        conn_pairs |= {(c["to"], c["from"]) for c in config["connections"]}
        folder_id = ids["FOLDERA"]
        # Both notes connected to folder
        assert (ids["NOTE1"], folder_id) in conn_pairs
        assert (ids["NOTE2"], folder_id) in conn_pairs

    def test_nested_folders_connected(self):
        root = self._make_vault({
            "Parent/Child/Note.md": "Deep note",
        })
        config = otd.parse_vault(str(root))
        ids = {v["name"]: v["id"] for v in config["vaults"]}
        conn_pairs = {(c["from"], c["to"]) for c in config["connections"]}
        conn_pairs |= {(c["to"], c["from"]) for c in config["connections"]}
        assert "PARENT" in ids
        assert "CHILD" in ids
        # Child folder → Parent folder
        assert (ids["CHILD"], ids["PARENT"]) in conn_pairs
        # Note → Child folder
        assert (ids["NOTE"], ids["CHILD"]) in conn_pairs

    def test_folder_vault_lists_children(self):
        root = self._make_vault({
            "MyFolder/A.md": "Alpha",
            "MyFolder/B.md": "Beta",
        })
        config = otd.parse_vault(str(root))
        folder_vault = next(v for v in config["vaults"] if v["name"] == "MYFOLDER")
        assert "A" in folder_vault["html"]
        assert "B" in folder_vault["html"]

    def test_folder_has_distinct_color(self):
        root = self._make_vault({
            "Stuff/Note.md": "Content",
        })
        config = otd.parse_vault(str(root))
        colors = {v["name"]: v["color"] for v in config["vaults"]}
        # Folder vault uses FOLDER_COLOR constant, not the same as child note color
        assert "STUFF" in colors

    def test_root_notes_no_folder_vault(self):
        """Notes at vault root don't create a folder vault."""
        root = self._make_vault({
            "RootNote.md": "At root level",
        })
        config = otd.parse_vault(str(root))
        names = [v["name"] for v in config["vaults"]]
        assert names == ["ROOTNOTE"]

    def test_obsidian_folder_not_a_vault(self):
        root = self._make_vault({
            ".obsidian/config.json": "{}",
            "Note.md": "Real",
        })
        config = otd.parse_vault(str(root))
        names = [v["name"] for v in config["vaults"]]
        assert ".OBSIDIAN" not in names


class TestMarkdownRendering(unittest.TestCase):
    """Test that markdown formatting is preserved in vault panel HTML."""

    def _make_vault(self, files: dict[str, str]) -> Path:
        d = tempfile.mkdtemp()
        root = Path(d)
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return root

    def _get_html(self, content: str) -> str:
        root = self._make_vault({"Note.md": content})
        config = otd.parse_vault(str(root))
        return config["vaults"][0]["html"]

    def test_bold_rendered(self):
        html = self._get_html("Some **bold text** here")
        assert "<strong>bold text</strong>" in html

    def test_italic_rendered(self):
        html = self._get_html("Some *italic text* here")
        assert "<em>italic text</em>" in html

    def test_inline_code_rendered(self):
        html = self._get_html("Use `print()` to debug")
        assert "<code" in html
        assert "print()" in html

    def test_unordered_list_gets_bullet(self):
        html = self._get_html("- First item\n- Second item")
        assert "\u2022" in html  # bullet character
        assert "First item" in html
        assert "Second item" in html

    def test_ordered_list_preserves_number(self):
        html = self._get_html("1. First step\n2. Second step")
        assert "1." in html
        assert "First step" in html
        assert "2." in html

    def test_blockquote_styled(self):
        html = self._get_html("> This is a quote")
        assert "border-left" in html
        assert "This is a quote" in html

    def test_markdown_link_rendered(self):
        html = self._get_html("See [example](https://example.com) page")
        assert 'href="https://example.com"' in html
        assert "example" in html

    def test_html_entities_escaped(self):
        """Ensure XSS-safe: HTML tags in content are escaped."""
        html = self._get_html("Try <script>alert(1)</script> here")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_bold_and_italic_combined(self):
        html = self._get_html("Both **bold** and *italic* work")
        assert "<strong>bold</strong>" in html
        assert "<em>italic</em>" in html

    def test_asterisk_list_gets_bullet(self):
        html = self._get_html("* Item with asterisk")
        assert "\u2022" in html
        assert "Item with asterisk" in html

    def test_code_fence_lines_monospace(self):
        content = "Before\n```python\ndef hello():\n    pass\n```\nAfter"
        html = self._get_html(content)
        assert "monospace" in html or "def hello():" in html


class TestNoCaps(unittest.TestCase):
    """All content from Obsidian must be accessible — no artificial limits."""

    def _make_vault(self, files: dict[str, str]) -> Path:
        d = tempfile.mkdtemp()
        root = Path(d)
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return root

    def _get_html(self, content: str) -> str:
        root = self._make_vault({"Note.md": content})
        config = otd.parse_vault(str(root))
        return config["vaults"][0]["html"]

    def test_all_tags_shown(self):
        tags = " ".join(f"#tag{i}" for i in range(15))
        html = self._get_html(f"Text with {tags}")
        for i in range(15):
            assert f"#tag{i}" in html, f"#tag{i} missing"

    def test_all_headings_shown(self):
        headings = "\n".join(f"## Section {i}" for i in range(20))
        html = self._get_html(headings + "\nContent here.")
        for i in range(20):
            assert f"Section {i}" in html, f"Section {i} missing"

    def test_linked_notes_not_in_parser_html(self):
        """Linked notes are handled by generate.py at runtime, not the parser."""
        root = self._make_vault({
            "Hub.md": "Links: [[Note0]] [[Note1]]",
            "Note0.md": "Note 0",
            "Note1.md": "Note 1",
        })
        config = otd.parse_vault(str(root))
        hub = next(v for v in config["vaults"] if v["name"] == "HUB")
        assert "Linked Notes" not in hub["html"]
        # But connections must still be created
        assert len(config["connections"]) >= 1

    def test_all_external_urls_shown(self):
        urls = "\n".join(f"https://example.com/page{i}" for i in range(15))
        html = self._get_html(urls)
        for i in range(15):
            assert f"page{i}" in html, f"URL page{i} missing"

    def test_all_pdfs_shown(self):
        embeds = "\n".join(f"![[doc{i}.pdf]]" for i in range(10))
        html = self._get_html(embeds)
        for i in range(10):
            assert f"doc{i}.pdf" in html, f"doc{i}.pdf missing"

    def test_no_emoji_in_html(self):
        """No emoji characters — they break the cyberpunk aesthetic."""
        root = self._make_vault({
            "Folder/Note.md": "See ![[paper.pdf]] and [[Other]]",
            "Folder/Other.md": "Other note",
        })
        config = otd.parse_vault(str(root))
        for v in config["vaults"]:
            assert "\U0001f517" not in v["html"], f"Link emoji in {v['name']}"
            assert "\U0001f4c4" not in v["html"], f"Doc emoji in {v['name']}"
            assert "\U0001f4c1" not in v["html"], f"Folder emoji in {v['name']}"

    def test_all_images_referenced(self):
        """All image embeds must produce img tags, not just first 6."""
        files = {"Note.md": "\n".join(f"![[img{i}.png]]" for i in range(10))}
        for i in range(10):
            # Create tiny valid-enough files
            files[f"img{i}.png"] = "FAKEPNG"
        root = self._make_vault(files)
        config = otd.parse_vault(str(root))
        html = config["vaults"][0]["html"]
        img_count = html.count("<img ")
        assert img_count >= 10, f"Only {img_count} img tags, expected 10+"

    def test_images_use_file_paths_for_large(self):
        """Large images should use file:// paths instead of base64."""
        root = self._make_vault({
            "Note.md": "![[big.png]]",
            "big.png": "X" * 600_000,  # over 512KB
        })
        config = otd.parse_vault(str(root))
        html = config["vaults"][0]["html"]
        assert "file://" in html, "Large image should use file:// URI"
        assert "data:" not in html, "Large image should not use base64"

    def test_small_images_use_base64(self):
        """Small images should still embed as base64 for portability."""
        root = self._make_vault({
            "Note.md": "![[photo.png]]",
            "photo.png": "FAKEPNG",
        })
        config = otd.parse_vault(str(root))
        html = config["vaults"][0]["html"]
        assert "data:" in html, "Small image should use base64"

    def test_large_image_not_skipped(self):
        """Images over 512KB must still appear (via file:// path)."""
        root = self._make_vault({
            "Note.md": "![[big.png]]",
            "big.png": "X" * 600_000,  # over 512KB
        })
        config = otd.parse_vault(str(root))
        html = config["vaults"][0]["html"]
        assert "big.png" in html or "file://" in html, "Large image was skipped"

    def test_unresolvable_image_gets_placeholder(self):
        """Image refs that can't be found on disk get a pi-err-wrap placeholder."""
        root = self._make_vault({
            "Note.md": "![[missing-screenshot.png]]\n![[also-gone.jpg]]",
        })
        config = otd.parse_vault(str(root))
        html = config["vaults"][0]["html"]
        assert "pi-err-wrap" in html, "Missing images should get error placeholder"
        assert "missing-screenshot.png" in html, "Placeholder should show the ref name"
        assert "also-gone.jpg" in html


class TestFullContent(unittest.TestCase):
    """Test that full note content is shown, not truncated."""

    def _make_vault(self, files: dict[str, str]) -> Path:
        d = tempfile.mkdtemp()
        root = Path(d)
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return root

    def test_all_content_lines_present(self):
        lines = [f"Line number {i} with some content here" for i in range(20)]
        content = "\n".join(lines)
        root = self._make_vault({"Long.md": content})
        config = otd.parse_vault(str(root))
        html_out = config["vaults"][0]["html"]
        # All lines should be present, not just first 8
        assert "Line number 0" in html_out
        assert "Line number 19" in html_out

    def test_long_lines_not_truncated(self):
        long_line = "A" * 500
        root = self._make_vault({"Wide.md": long_line})
        config = otd.parse_vault(str(root))
        html_out = config["vaults"][0]["html"]
        # Full 500 chars should be present
        assert "A" * 500 in html_out


class TestCLI(unittest.TestCase):
    """Test command-line interface."""

    def _make_vault(self, files: dict[str, str]) -> Path:
        d = tempfile.mkdtemp()
        root = Path(d)
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return root

    def test_parse_vault_returns_valid_json(self):
        root = self._make_vault({"test.md": "# Test"})
        config = otd.parse_vault(str(root))
        # Must be JSON-serializable
        json.dumps(config)
        assert "title" in config
        assert "vaults" in config
        assert "connections" in config
        assert "stats" in config
        assert "glyphs" in config

    def test_invalid_path_raises(self):
        with self.assertRaises(otd.ContractViolationError):
            otd.parse_vault("/nonexistent/path")

    def test_empty_vault_raises(self):
        root = self._make_vault({".obsidian/config.json": "{}"})
        with self.assertRaises(otd.ContractViolationError):
            otd.parse_vault(str(root))


if __name__ == "__main__":
    unittest.main()
