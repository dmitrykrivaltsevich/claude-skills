"""Tests for lint.py — mechanical KB health checks."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import init
import lint
from contracts import ContractViolationError


@pytest.fixture
def kb_path(tmp_path: Path) -> Path:
    p = tmp_path / "test-kb"
    init.scaffold_kb(str(p), "Test KB")
    return p


def _write_entry(kb_path: Path, rel_path: str, content: str) -> Path:
    """Helper to write a knowledge entry file."""
    f = kb_path / rel_path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    return f


class TestBrokenLinks:
    def test_detects_broken_wikilink(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/topics/quantum.md", """---
type: topic
created: 2026-04-07
updated: 2026-04-07
source-ids: []
tags: []
---

# Quantum Computing

See also [[nonexistent-page]].
""")
        result = lint.lint_kb(str(kb_path))
        broken = [i for i in result["issues"] if i["type"] == "broken-link"]
        assert len(broken) >= 1
        assert "nonexistent-page" in broken[0]["target"]

    def test_valid_link_not_flagged(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/topics/quantum.md", """---
type: topic
created: 2026-04-07
updated: 2026-04-07
source-ids: []
tags: []
---

# Quantum Computing

See also [[ai-safety]].
""")
        _write_entry(kb_path, "knowledge/topics/ai-safety.md", """---
type: topic
created: 2026-04-07
updated: 2026-04-07
source-ids: []
tags: []
---

# AI Safety
""")
        result = lint.lint_kb(str(kb_path))
        broken = [i for i in result["issues"] if i["type"] == "broken-link"]
        assert len(broken) == 0

    def test_source_stub_link_not_flagged(self, kb_path: Path):
        """Wikilinks to source stubs in sources/ should not be flagged as broken."""
        _write_entry(kb_path, "sources/references/real-2020.md",
                     "---\ntype: source-reference\nsource-id: real-2020\n---\n# Real 2020\n")
        _write_entry(kb_path, "knowledge/sources/real-2020-analysis.md", """---
type: source-analysis
created: 2026-04-07
updated: 2026-04-07
source-ids: [real-2020]
tags: []
---

# real-2020 — Paper Title

**Source**: [[real-2020]]
""")
        result = lint.lint_kb(str(kb_path))
        broken = [i for i in result["issues"] if i["type"] == "broken-link"]
        assert len(broken) == 0


class TestOrphanPages:
    def test_detects_orphan(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/topics/orphan.md", """---
type: topic
created: 2026-04-07
updated: 2026-04-07
source-ids: []
tags: []
---

# Orphan Topic

No other page links here.
""")
        result = lint.lint_kb(str(kb_path))
        orphans = [i for i in result["issues"] if i["type"] == "orphan"]
        orphan_files = [i["file"] for i in orphans]
        assert any("orphan.md" in f for f in orphan_files)


class TestMissingBidirectional:
    def test_detects_one_way_link(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/topics/quantum.md", """---
type: topic
created: 2026-04-07
updated: 2026-04-07
source-ids: []
tags: []
---

# Quantum Computing

Related: [[ai-safety]]
""")
        _write_entry(kb_path, "knowledge/topics/ai-safety.md", """---
type: topic
created: 2026-04-07
updated: 2026-04-07
source-ids: []
tags: []
---

# AI Safety

No link back to quantum.
""")
        result = lint.lint_kb(str(kb_path))
        one_way = [i for i in result["issues"] if i["type"] == "missing-backlink"]
        assert len(one_way) >= 1


class TestMissingFrontmatter:
    def test_detects_missing_frontmatter(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/topics/no-fm.md",
                     "# No Frontmatter\n\nJust content.\n")
        result = lint.lint_kb(str(kb_path))
        fm_issues = [i for i in result["issues"] if i["type"] == "missing-frontmatter"]
        assert len(fm_issues) >= 1


class TestTimelineGaps:
    def test_detects_missing_prev_next(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/timeline/years/2025.md", """---
type: timeline
created: 2026-04-07
updated: 2026-04-07
source-ids: []
tags: []
---

# 2025

Events in 2025.
""")
        _write_entry(kb_path, "knowledge/timeline/years/2027.md", """---
type: timeline
created: 2026-04-07
updated: 2026-04-07
source-ids: []
tags: []
---

# 2027

Events in 2027.
""")
        result = lint.lint_kb(str(kb_path))
        timeline_issues = [i for i in result["issues"] if i["type"] == "timeline-gap"]
        # Should detect gap: 2025 has no next=2026, 2027 has no prev=2026
        assert len(timeline_issues) >= 1


class TestSummary:
    def test_returns_summary_counts(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/topics/test.md",
                     "# No frontmatter\n\n[[broken-link]]\n")
        result = lint.lint_kb(str(kb_path))
        assert "total_issues" in result
        assert result["total_issues"] > 0
        assert "issues" in result

    def test_clean_kb_has_zero_issues(self, kb_path: Path):
        # Fresh KB with no knowledge entries should be clean
        result = lint.lint_kb(str(kb_path))
        # index.md and log.md are outside knowledge/ — not checked for frontmatter
        knowledge_issues = [
            i for i in result["issues"]
            if "index.md" not in i.get("file", "") and "log.md" not in i.get("file", "")
        ]
        assert len(knowledge_issues) == 0


class TestCli:
    def test_lint_cli(self, kb_path: Path, capsys):
        lint.main(["--path", str(kb_path)])
        out = json.loads(capsys.readouterr().out)
        assert "total_issues" in out
