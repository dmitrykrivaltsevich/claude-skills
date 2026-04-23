"""Guardrail tests for practical-knowledge guidance propagation."""

from __future__ import annotations

from pathlib import Path


KB_DIR = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (KB_DIR / rel_path).read_text(encoding="utf-8")


class TestPracticalGuidance:
    def test_init_templates_expose_practical_guidance(self):
        init_script = _read("scripts/init.py")

        assert "idea-kind: conceptual | practical" in init_script
        assert "## Know-How" in init_script
        assert "## Hidden Gems" in init_script
        assert "## Pitfalls / Failure Modes" in init_script

    def test_entry_types_define_practical_idea_subtype(self):
        entry_types = _read("references/entry-types.md")

        assert "idea-kind: conceptual | practical" in entry_types
        assert "## Rule of thumb" in entry_types
        assert "## Use when" in entry_types
        assert "## Avoid when" in entry_types
        assert "## Trade-offs" in entry_types
        assert "## Failure modes" in entry_types
        assert "## Implementation notes" in entry_types

    def test_practical_workflow_is_referenced_across_kb_docs(self):
        practical_workflow = _read("references/practical-extraction.md")
        skill_doc = _read("SKILL.md")
        add_workflow = _read("references/add-workflow.md")
        article_workflow = _read("references/article-workflow.md")
        paper_workflow = _read("references/paper-workflow.md")
        video_workflow = _read("references/video-url-workflow.md")
        collection_workflow = _read("references/collection-workflow.md")
        book_workflow = _read("references/book-workflow.md")

        assert "no practical insight justified" in practical_workflow
        assert "references/practical-extraction.md" in skill_doc
        assert "practical-extraction.md" in add_workflow
        assert "practical-extraction.md" in article_workflow
        assert "practical-extraction.md" in paper_workflow
        assert "practical-extraction.md" in video_workflow
        assert "practical-extraction.md" in collection_workflow
        assert "practical-extraction.md" in book_workflow