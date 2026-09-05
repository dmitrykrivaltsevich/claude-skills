"""Tests for lint.py — mechanical KB health checks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ._loader import load_script_module

init = load_script_module("kb_test_lint_init", "init.py")
lint = load_script_module("kb_test_lint_script", "lint.py")
ContractViolationError = lint.ContractViolationError

try:
    _style_exceptions = load_script_module("kb_test_lint_style_exceptions", "style_exceptions.py")
except Exception as exc:  # red phase: module is not implemented yet
    _style_exceptions = None
    _style_exceptions_load_error = exc


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


@pytest.fixture
def style_exceptions():
    if _style_exceptions is None:
        pytest.fail(f"style_exceptions.py is not importable: {_style_exceptions_load_error}")
    return _style_exceptions


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

    def test_detects_month_gaps(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/timeline/months/2025-01.md", """---
type: timeline
created: 2026-04-07
updated: 2026-04-07
source-ids: []
tags: []
date: "2025-01"
---

# 2025-01
""")
        _write_entry(kb_path, "knowledge/timeline/months/2025-04.md", """---
type: timeline
created: 2026-04-07
updated: 2026-04-07
source-ids: []
tags: []
date: "2025-04"
---

# 2025-04
""")
        result = lint.lint_kb(str(kb_path))
        month_gaps = [i for i in result["issues"]
                      if i["type"] == "timeline-gap" and "months" in i["file"]]
        missing = {i["details"]["missing"] for i in month_gaps}
        assert "2025-02" in missing
        assert "2025-03" in missing

    def test_detects_month_gaps_across_year_boundary(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/timeline/months/2024-11.md", """---
type: timeline
date: "2024-11"
---
# 2024-11
""")
        _write_entry(kb_path, "knowledge/timeline/months/2025-02.md", """---
type: timeline
date: "2025-02"
---
# 2025-02
""")
        result = lint.lint_kb(str(kb_path))
        month_gaps = [i for i in result["issues"]
                      if i["type"] == "timeline-gap" and "months" in i["file"]]
        missing = {i["details"]["missing"] for i in month_gaps}
        assert "2024-12" in missing
        assert "2025-01" in missing

    def test_detects_day_gaps(self, kb_path: Path):
        _write_entry(kb_path, "knowledge/timeline/days/2025-03-10.md", """---
type: timeline
date: "2025-03-10"
---
# 2025-03-10
""")
        _write_entry(kb_path, "knowledge/timeline/days/2025-03-13.md", """---
type: timeline
date: "2025-03-13"
---
# 2025-03-13
""")
        result = lint.lint_kb(str(kb_path))
        day_gaps = [i for i in result["issues"]
                    if i["type"] == "timeline-gap" and "days" in i["file"]]
        missing = {i["details"]["missing"] for i in day_gaps}
        assert "2025-03-11" in missing
        assert "2025-03-12" in missing


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


class TestPathValidation:
    def test_rejects_nonexistent_kb_path(self, tmp_path: Path):
        with pytest.raises(ContractViolationError, match="(?i)existing KB directory"):
            lint.lint_kb(str(tmp_path / "nonexistent"))

    def test_rejects_file_path(self, tmp_path: Path):
        file_path = tmp_path / "a-file.md"
        file_path.write_text("not a directory\n", encoding="utf-8")
        with pytest.raises(ContractViolationError, match="(?i)existing KB directory"):
            lint.lint_kb(str(file_path))

    def test_existing_empty_dir_is_ok(self, tmp_path: Path):
        empty_kb = tmp_path / "empty-kb"
        empty_kb.mkdir()
        result = lint.lint_kb(str(empty_kb))
        assert result["issues"] == []
        assert result["total_issues"] == 0

    def test_rejects_non_string_kb_path(self):
        for bad in (None, 42, []):
            with pytest.raises(ContractViolationError, match="(?i)non-empty"):
                lint.lint_kb(bad)

    def test_accepts_path_object(self, kb_path: Path):
        """Siblings accept str | Path; lint must not be the one that raises AttributeError."""
        result = lint.lint_kb(kb_path)
        assert "total_issues" in result

    def test_cli_missing_path_exits_nonzero(self, tmp_path: Path, capsys):
        with pytest.raises(SystemExit) as exc_info:
            lint.main(["--path", str(tmp_path / "nonexistent")])
        assert exc_info.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert "error" in err


_DEFAULT_STYLE_SAMPLES = {
    "load-bearing": "load-bearing",
    "not-just-contrast": "not just fast but cheap",
    "the-key-insight": "the key insight",
    "paradigm-shift": "paradigm-shift",
    "crucially": "crucially",
    "deep-dive": "deep dive",
    "tapestry": "tapestry",
    "underscores": "underscores",
    "delve": "delve",
    "testament-to": "testament to",
    "claude-vocabulary": "multifaceted",
    "pivotal": "pivotal",
    "showcases": "showcases",
    "seamless": "seamless",
    "realm-of": "in the realm of",
    "throat-clearing": "it's worth noting",
    "claude-ritual": "one might argue",
    "weasel-attribution": "studies show",
    "filler-frames": "in today's digital age",
    "hype": "game-changer",
    "litotes": "far from trivial",
    "intricate": "intricate",
    "real-reframe": "that's the real cost",
    "comparative-kicker": "It matters, and it's bigger than expected",
    "antithesis-pivot": "That's not a wart. That's a fork",
    "heres-the-thing": "here's the thing",
    "the-point-is": "which is exactly the point",
    "directness-signal": "to be blunt",
    "upshot-frame": "the upshot",
    "self-answered-question": "Why does this matter? Because the count lies",
    "worth-preamble": "worth knowing",
    "weight-metaphor": "does the heavy lifting",
}


def _style_phrase_issues(result: dict, *, pattern: str | None = None, file: str | None = None) -> list[dict]:
    out = []
    for issue in result.get("issues", []):
        if issue.get("type") != "style-phrase":
            continue
        if pattern is not None and issue.get("pattern") != pattern:
            continue
        if file is not None and issue.get("file") != file:
            continue
        out.append(issue)
    return out


def _entry_markdown(title: str, body: str) -> str:
    return f"""---
type: topic
created: 2026-04-07
updated: 2026-04-07
source-ids: []
tags: []
---

# {title}

{body}
"""


class TestStylePhrases:
    def test_prose_phrase_flagged(self, kb_path: Path):
        _write_entry(
            kb_path,
            "knowledge/topics/slop.md",
            _entry_markdown("Slop", "This uses load-bearing details."),
        )
        result = lint.lint_kb(str(kb_path))
        issues = _style_phrase_issues(result, pattern="load-bearing")
        assert len(issues) == 1
        issue = issues[0]
        assert issue["file"] == "knowledge/topics/slop.md"
        assert issue["line"] == 11
        assert issue["column"] == 11
        assert issue["match"] == "load-bearing"
        assert issue["context"] == "prose"
        assert "load-bearing" in issue["excerpt"]
        assert issue["excepted"] is False
        assert issue["note"]

    def test_every_default_pattern_matches_its_sample(self, kb_path: Path):
        body = "\n".join(f"- {text}" for text in _DEFAULT_STYLE_SAMPLES.values())
        _write_entry(
            kb_path,
            "knowledge/topics/all-styles.md",
            _entry_markdown("All style samples", body),
        )
        result = lint.lint_kb(str(kb_path))
        found = {issue["pattern"] for issue in _style_phrase_issues(result)}
        assert set(_DEFAULT_STYLE_SAMPLES) <= found

    def test_blockquote_is_quote_context(self, kb_path: Path):
        _write_entry(
            kb_path,
            "knowledge/topics/blockquote.md",
            _entry_markdown("Blockquote", "> Crucially, this is cited context."),
        )
        result = lint.lint_kb(str(kb_path))
        issues = _style_phrase_issues(result, pattern="crucially")
        assert len(issues) == 1
        assert issues[0]["context"] == "quote"

    def test_straight_inline_quote_is_quote_context(self, kb_path: Path):
        _write_entry(
            kb_path,
            "knowledge/topics/straight-quote.md",
            _entry_markdown("Straight quote", 'He said "crucially" without emphasis.'),
        )
        result = lint.lint_kb(str(kb_path))
        issues = _style_phrase_issues(result, pattern="crucially")
        assert len(issues) == 1
        assert issues[0]["context"] == "quote"

    def test_curly_inline_quote_is_quote_context(self, kb_path: Path):
        _write_entry(
            kb_path,
            "knowledge/topics/curly-quote.md",
            _entry_markdown("Curly quote", "She said “crucially” without emphasis."),
        )
        result = lint.lint_kb(str(kb_path))
        issues = _style_phrase_issues(result, pattern="crucially")
        assert len(issues) == 1
        assert issues[0]["context"] == "quote"

    def test_inline_code_not_flagged(self, kb_path: Path):
        _write_entry(
            kb_path,
            "knowledge/topics/code-span.md",
            _entry_markdown("Code span", "The literal word `crucially` stays untouched."),
        )
        result = lint.lint_kb(str(kb_path))
        assert _style_phrase_issues(result) == []

    def test_fenced_code_not_flagged(self, kb_path: Path):
        _write_entry(
            kb_path,
            "knowledge/topics/fenced-code.md",
            _entry_markdown("Fenced code", "```\ncrucially\n```"),
        )
        result = lint.lint_kb(str(kb_path))
        assert _style_phrase_issues(result) == []

    def test_frontmatter_not_flagged(self, kb_path: Path):
        _write_entry(
            kb_path,
            "knowledge/topics/sloppy-frontmatter.md",
            """---
type: topic
created: 2026-04-07
updated: 2026-04-07
source-ids: []
tags:
  - crucially
---

# Frontmatter

No phrase here.
""",
        )
        result = lint.lint_kb(str(kb_path))
        assert _style_phrase_issues(result) == []

    def test_heading_context(self, kb_path: Path):
        _write_entry(
            kb_path,
            "knowledge/topics/heading.md",
            _entry_markdown("Crucially important", "No phrase here."),
        )
        result = lint.lint_kb(str(kb_path))
        issues = _style_phrase_issues(result, pattern="crucially")
        assert len(issues) == 1
        assert issues[0]["context"] == "heading"

    def test_log_md_scanned(self, kb_path: Path):
        (kb_path / "log.md").write_text(
            "# Log\n\nThis is load-bearing.\n", encoding="utf-8"
        )
        result = lint.lint_kb(str(kb_path))
        issues = _style_phrase_issues(result, pattern="load-bearing", file="log.md")
        assert len(issues) == 1

    def test_index_md_scanned(self, kb_path: Path):
        (kb_path / "index.md").write_text(
            "# Index\n\ncrucially\n", encoding="utf-8"
        )
        result = lint.lint_kb(str(kb_path))
        issues = _style_phrase_issues(result, pattern="crucially", file="index.md")
        assert len(issues) == 1

    def test_rules_md_scanned(self, kb_path: Path):
        (kb_path / ".kb" / "rules.md").write_text(
            "# Rules\n\nseamless\n", encoding="utf-8"
        )
        result = lint.lint_kb(str(kb_path))
        issues = _style_phrase_issues(result, pattern="seamless", file=".kb/rules.md")
        assert len(issues) == 1

    def test_source_reference_stub_scanned(self, kb_path: Path):
        _write_entry(
            kb_path,
            "sources/references/real-2020.md",
            "---\ntype: source-reference\nsource-id: real-2020\n---\n# Real 2020\n\ntestament to\n",
        )
        result = lint.lint_kb(str(kb_path))
        issues = _style_phrase_issues(result, pattern="testament-to", file="sources/references/real-2020.md")
        assert len(issues) == 1

    def test_bare_encompass_flagged(self, kb_path: Path):
        _write_entry(
            kb_path,
            "knowledge/topics/bare.md",
            _entry_markdown("Bare", "These entries encompass three areas."),
        )
        result = lint.lint_kb(str(kb_path))
        issues = _style_phrase_issues(result, pattern="claude-vocabulary")
        assert len(issues) == 1
        assert issues[0]["match"] == "encompass"

    def test_longer_fence_not_closed_by_shorter_run(self, kb_path: Path):
        _write_entry(
            kb_path,
            "knowledge/topics/nested-fence.md",
            _entry_markdown("Nested fence", "````\n```\ncrucially\n```\n````"),
        )
        result = lint.lint_kb(str(kb_path))
        assert _style_phrase_issues(result) == []

    def test_info_string_line_does_not_close_fence(self, kb_path: Path):
        _write_entry(
            kb_path,
            "knowledge/topics/info-fence.md",
            _entry_markdown("Info fence", "```\ncrucially\n```python\ndelve\n```"),
        )
        result = lint.lint_kb(str(kb_path))
        assert _style_phrase_issues(result) == []

    def test_tilde_fence_not_closed_by_backticks(self, kb_path: Path):
        _write_entry(
            kb_path,
            "knowledge/topics/tilde-fence.md",
            _entry_markdown("Tilde fence", "~~~\n```\ncrucially\n~~~"),
        )
        result = lint.lint_kb(str(kb_path))
        assert _style_phrase_issues(result) == []

    def test_question_heading_alone_is_not_flagged(self, kb_path: Path):
        """A heading phrased as a question is normal KB structure, not slop."""
        _write_entry(
            kb_path,
            "knowledge/topics/question-heading.md",
            _entry_markdown("Convergence", "## Why does the algorithm converge?\n\nIt converges because the step size shrinks."),
        )
        result = lint.lint_kb(str(kb_path))
        assert _style_phrase_issues(result, pattern="self-answered-question") == []

    def test_self_answered_question_flagged(self, kb_path: Path):
        _write_entry(
            kb_path,
            "knowledge/topics/self-answer.md",
            _entry_markdown("Self answer", "Why does this matter? Because the count lies."),
        )
        result = lint.lint_kb(str(kb_path))
        assert len(_style_phrase_issues(result, pattern="self-answered-question")) == 1

    def test_absolute_path_exception_suppresses_finding(self, kb_path: Path, style_exceptions):
        """An exception keyed by absolute path must match the finding it was recorded for."""
        _write_entry(
            kb_path,
            "knowledge/topics/slop.md",
            _entry_markdown("Slop", "This uses load-bearing details."),
        )
        issue = _style_phrase_issues(lint.lint_kb(str(kb_path)), pattern="load-bearing")[0]
        style_exceptions.add_exception(
            str(kb_path),
            str(kb_path / issue["file"]),
            issue["line"],
            issue["pattern"],
            issue["match"],
            reason="subject-matter",
        )
        second = lint.lint_kb(str(kb_path))
        assert _style_phrase_issues(second, pattern="load-bearing") == []
        assert second["style"]["exceptions"] == 1

    def test_dot_slash_path_exception_suppresses_finding(self, kb_path: Path, style_exceptions):
        _write_entry(
            kb_path,
            "knowledge/topics/slop.md",
            _entry_markdown("Slop", "This uses load-bearing details."),
        )
        issue = _style_phrase_issues(lint.lint_kb(str(kb_path)), pattern="load-bearing")[0]
        style_exceptions.add_exception(
            str(kb_path),
            "./" + issue["file"],
            issue["line"],
            issue["pattern"],
            issue["match"],
            reason="subject-matter",
        )
        second = lint.lint_kb(str(kb_path))
        assert _style_phrase_issues(second, pattern="load-bearing") == []

    def test_backslash_path_exception_suppresses_finding(self, kb_path: Path, style_exceptions):
        _write_entry(
            kb_path,
            "knowledge/topics/slop.md",
            _entry_markdown("Slop", "This uses load-bearing details."),
        )
        issue = _style_phrase_issues(lint.lint_kb(str(kb_path)), pattern="load-bearing")[0]
        style_exceptions.add_exception(
            str(kb_path),
            issue["file"].replace("/", "\\"),
            issue["line"],
            issue["pattern"],
            issue["match"],
            reason="subject-matter",
        )
        second = lint.lint_kb(str(kb_path))
        assert _style_phrase_issues(second, pattern="load-bearing") == []

    def test_unreadable_markdown_is_reported_once_not_raised(self, kb_path: Path):
        bad = kb_path / "knowledge" / "topics" / "bad.md"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_bytes(b"---\ntype: topic\n---\n\n\xff\xfe not utf-8\n")
        _write_entry(
            kb_path,
            "knowledge/topics/good.md",
            _entry_markdown("Good", "This uses load-bearing details."),
        )
        result = lint.lint_kb(str(kb_path))
        unreadable = [i for i in result["issues"] if i["type"] == "unreadable-file"]
        assert len(unreadable) == 1, "must be reported once, not once per scanning pass"
        assert unreadable[0]["file"] == "knowledge/topics/bad.md"
        assert unreadable[0]["message"]
        # The rest of the lint still runs.
        assert _style_phrase_issues(result, file="knowledge/topics/good.md")

    def test_unreadable_file_not_flagged_as_orphan_or_missing_backlink(self, kb_path: Path):
        """Never tell the model to edit a file it could not read."""
        bad = kb_path / "knowledge" / "topics" / "bad.md"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_bytes(b"---\ntype: topic\n---\n\n\xff\xfe not utf-8\n")
        _write_entry(
            kb_path,
            "knowledge/topics/good.md",
            _entry_markdown("Good", "Links to [[bad]] here."),
        )
        result = lint.lint_kb(str(kb_path))
        by_type = lambda kind: [i for i in result["issues"] if i["type"] == kind]

        assert [i["file"] for i in by_type("unreadable-file")] == ["knowledge/topics/bad.md"]
        assert not [i for i in by_type("orphan") if "bad.md" in i["file"]]
        assert not [i for i in by_type("missing-backlink") if "bad.md" in i["file"]]
        # Readable files are still checked normally.
        assert [i for i in by_type("orphan") if "good.md" in i["file"]]

    def test_quoted_phrase_in_heading_is_context_quote(self, kb_path: Path):
        """Rule 2 (verbatim-quote) must reach quotations wherever they appear."""
        _write_entry(
            kb_path,
            "knowledge/topics/quoted-heading.md",
            _entry_markdown("Quoted heading", '## He said "crucially" in the talk'),
        )
        result = lint.lint_kb(str(kb_path))
        issues = _style_phrase_issues(result, pattern="crucially")
        assert len(issues) == 1
        assert issues[0]["context"] == "quote"

    def test_unquoted_phrase_in_heading_stays_heading(self, kb_path: Path):
        _write_entry(
            kb_path,
            "knowledge/topics/plain-heading.md",
            _entry_markdown("Plain heading", "## Why crucially matters"),
        )
        result = lint.lint_kb(str(kb_path))
        issues = _style_phrase_issues(result, pattern="crucially")
        assert len(issues) == 1
        assert issues[0]["context"] == "heading"

    def test_frontmatter_checks_agree_on_junk_close(self, kb_path: Path):
        """A block that is not frontmatter for one check must not be for the other."""
        path = kb_path / "knowledge" / "topics" / "junk-close.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\ntitle: crucially important\n---junk\n\nBody.\n", encoding="utf-8")
        result = lint.lint_kb(str(kb_path))
        missing = [
            i for i in result["issues"]
            if i["type"] == "missing-frontmatter" and "junk-close.md" in i["file"]
        ]
        scanned = _style_phrase_issues(result, file="knowledge/topics/junk-close.md")
        # Not valid frontmatter -> reported as missing, and its lines are prose.
        assert len(missing) == 1
        assert len(scanned) == 1

    def test_frontmatter_checks_agree_on_indented_close(self, kb_path: Path):
        path = kb_path / "knowledge" / "topics" / "indented-close.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\ntitle: crucially important\n  ---  \n\nBody.\n", encoding="utf-8")
        result = lint.lint_kb(str(kb_path))
        missing = [
            i for i in result["issues"]
            if i["type"] == "missing-frontmatter" and "indented-close.md" in i["file"]
        ]
        scanned = _style_phrase_issues(result, file="knowledge/topics/indented-close.md")
        # Valid frontmatter for both checks -> not missing, and not scanned.
        assert missing == []
        assert scanned == []

    def test_kb_machinery_files_excluded(self, kb_path: Path):
        """kb:lint writes rules-proposals.md and task state; it must not then flag them."""
        (kb_path / ".kb" / "rules-proposals.md").write_text(
            "# Proposals\n\nThis rule is load-bearing.\n", encoding="utf-8"
        )
        (kb_path / ".kb" / "tasks").mkdir(parents=True, exist_ok=True)
        (kb_path / ".kb" / "tasks" / "task-1.md").write_text(
            "# Task\n\nA load-bearing note.\n", encoding="utf-8"
        )
        result = lint.lint_kb(str(kb_path))
        assert _style_phrase_issues(result, file=".kb/rules-proposals.md") == []
        assert _style_phrase_issues(result, file=".kb/tasks/task-1.md") == []

    def test_style_exception_store_excluded(self, kb_path: Path):
        """The exception store explains itself in prose; lint must not flag its own store."""
        store = kb_path / ".kb" / "style-exceptions"
        store.mkdir(parents=True, exist_ok=True)
        (store / "README.md").write_text(
            "# Style exceptions\n\nEvery record here is load-bearing.\n", encoding="utf-8"
        )
        legacy = kb_path / ".kb" / "style-reviewed"
        legacy.mkdir(parents=True, exist_ok=True)
        (legacy / "README.md").write_text(
            "# Old store\n\nEvery record here is load-bearing.\n", encoding="utf-8"
        )
        result = lint.lint_kb(str(kb_path))
        assert _style_phrase_issues(result, file=".kb/style-exceptions/README.md") == []
        assert _style_phrase_issues(result, file=".kb/style-reviewed/README.md") == []

    def test_lint_does_not_migrate_the_legacy_store(self, kb_path: Path):
        """lint is read-only: it reads both locations and moves nothing."""
        legacy = kb_path / ".kb" / "style-reviewed"
        legacy.mkdir(parents=True, exist_ok=True)
        _write_entry(
            kb_path,
            "knowledge/topics/quoted.md",
            _entry_markdown("Quoted", 'He said "this is load-bearing" once.\n'),
        )
        first = lint.lint_kb(str(kb_path))
        finding = _style_phrase_issues(first, file="knowledge/topics/quoted.md")
        assert len(finding) == 1
        (legacy / "a.json").write_text(
            json.dumps(
                {
                    "schema": "kb-style-review/v1",
                    "key": {
                        "file": "knowledge/topics/quoted.md",
                        "line": finding[0]["line"],
                        "pattern": finding[0]["pattern"],
                        "match": finding[0]["match"],
                    },
                    "reason": "verbatim-quote",
                    "created": "2026-01-01T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )

        result = lint.lint_kb(str(kb_path))

        assert _style_phrase_issues(result, file="knowledge/topics/quoted.md") == []
        assert result["style"]["exceptions"] == 1
        assert legacy.is_dir(), "a read-only lint must not move the legacy store"
        assert not (kb_path / ".kb" / "style-exceptions").exists()

    def test_kb_rules_file_is_still_scanned(self, kb_path: Path):
        """rules.md is durable prose, not run state — it stays in scope."""
        (kb_path / ".kb" / "rules.md").write_text(
            "# Rules\n\nEntries are load-bearing.\n", encoding="utf-8"
        )
        result = lint.lint_kb(str(kb_path))
        assert len(_style_phrase_issues(result, file=".kb/rules.md")) == 1

    def test_indented_code_block_not_flagged(self, kb_path: Path):
        _write_entry(
            kb_path,
            "knowledge/topics/indented.md",
            _entry_markdown("Indented", "Example:\n\n    crucially = compute()\n"),
        )
        result = lint.lint_kb(str(kb_path))
        assert _style_phrase_issues(result, pattern="crucially") == []

    def test_indented_list_continuation_is_still_prose(self, kb_path: Path):
        """A 4-space indent under a list item is continuation text, not a code block."""
        _write_entry(
            kb_path,
            "knowledge/topics/list-cont.md",
            _entry_markdown("List", "- an item\n    crucially this matters\n"),
        )
        result = lint.lint_kb(str(kb_path))
        assert len(_style_phrase_issues(result, pattern="crucially")) == 1

    def test_indented_paragraph_continuation_is_still_prose(self, kb_path: Path):
        """An indented line directly after text is a lazy continuation, not code."""
        _write_entry(
            kb_path,
            "knowledge/topics/para-cont.md",
            _entry_markdown("Para", "Some sentence\n    crucially continued here\n"),
        )
        result = lint.lint_kb(str(kb_path))
        assert len(_style_phrase_issues(result, pattern="crucially")) == 1

    def test_sources_files_excluded(self, kb_path: Path):
        _write_entry(
            kb_path,
            "sources/files/real-2020/description.md",
            "---\n\ntestament to\n",
        )
        result = lint.lint_kb(str(kb_path))
        assert _style_phrase_issues(result) == []

    def test_exception_moves_finding_out_of_outstanding_work(self, kb_path: Path, style_exceptions):
        _write_entry(
            kb_path,
            "knowledge/topics/slop.md",
            _entry_markdown("Slop", "This uses load-bearing details."),
        )
        first = lint.lint_kb(str(kb_path))
        issue = _style_phrase_issues(first, pattern="load-bearing")[0]
        style_exceptions.add_exception(
            str(kb_path),
            issue["file"],
            issue["line"],
            issue["pattern"],
            issue["match"],
            reason="other",
        )
        second = lint.lint_kb(str(kb_path))
        assert _style_phrase_issues(second, pattern="load-bearing") == []
        assert second["style"]["findings"] == 0
        assert second["style"]["exceptions"] == 1
        recorded = second["style"]["exception_findings"]
        assert len(recorded) == 1
        assert recorded[0]["excepted"] is True
        assert recorded[0]["match"] == "load-bearing"

    def test_excepting_every_finding_leaves_no_style_work(self, kb_path: Path, style_exceptions):
        """A fully triaged KB must not carry a permanent non-zero lint count."""
        _write_entry(
            kb_path,
            "knowledge/topics/slop.md",
            _entry_markdown("Slop", "This load-bearing tapestry showcases the key insight."),
        )
        mechanical_only = lint.lint_kb(str(kb_path), style_enabled=False)["total_issues"]

        findings = _style_phrase_issues(lint.lint_kb(str(kb_path)))
        assert len(findings) >= 4
        for finding in findings:
            style_exceptions.add_exception(
                str(kb_path),
                finding["file"],
                finding["line"],
                finding["pattern"],
                finding["match"],
                reason="subject-matter",
            )

        after = lint.lint_kb(str(kb_path))
        assert _style_phrase_issues(after) == []
        assert after["total_issues"] == mechanical_only
        assert after["style"]["exceptions"] == len(findings)

    def test_total_issues_equals_outstanding_issue_list(self, kb_path: Path, style_exceptions):
        _write_entry(
            kb_path,
            "knowledge/topics/slop.md",
            _entry_markdown("Slop", "This load-bearing note is crucially delving."),
        )
        first = lint.lint_kb(str(kb_path))
        issue = _style_phrase_issues(first, pattern="load-bearing")[0]
        style_exceptions.add_exception(
            str(kb_path),
            issue["file"],
            issue["line"],
            issue["pattern"],
            issue["match"],
            reason="subject-matter",
        )
        second = lint.lint_kb(str(kb_path))
        assert second["total_issues"] == len(second["issues"])
        assert all(not i.get("excepted", False) for i in second["issues"])
        assert second["total_issues"] == first["total_issues"] - 1

    def test_stale_exception_does_not_suppress(self, kb_path: Path, style_exceptions):
        _write_entry(
            kb_path,
            "knowledge/topics/slop.md",
            _entry_markdown("Slop", "This uses load-bearing details."),
        )
        first = lint.lint_kb(str(kb_path))
        issue = _style_phrase_issues(first, pattern="load-bearing")[0]
        style_exceptions.add_exception(
            str(kb_path),
            issue["file"],
            issue["line"] + 1,
            issue["pattern"],
            issue["match"],
            reason="other",
        )
        second = lint.lint_kb(str(kb_path))
        current = _style_phrase_issues(second, pattern="load-bearing")
        assert current
        assert current[0]["excepted"] is False
        assert second["style"]["findings"] == 1
        assert second["style"]["exceptions"] == 0

    def test_style_summary_shape(self, kb_path: Path):
        _write_entry(
            kb_path,
            "knowledge/topics/summary.md",
            _entry_markdown("Summary", "This is a load-bearing tapestry."),
        )
        result = lint.lint_kb(str(kb_path))
        style = result["style"]
        assert style["findings"] == 2
        assert style["exceptions"] == 0
        assert style["exception_findings"] == []
        assert style["by_context"]["prose"] == 2
        assert style["by_pattern"]["load-bearing"] == 1
        assert style["by_pattern"]["tapestry"] == 1
        assert style["by_source"]["default"] == 2
        assert style["disabled"] == []
        assert result["total_issues"] >= 2

    def test_no_style_disables_scan(self, kb_path: Path):
        _write_entry(
            kb_path,
            "knowledge/topics/slop.md",
            _entry_markdown("Slop", "This uses load-bearing details."),
        )
        result = lint.lint_kb(str(kb_path), style_enabled=False)
        assert _style_phrase_issues(result) == []
        assert result["style"]["findings"] == 0
        assert result["style"]["exceptions"] == 0

    def test_cli_no_style(self, kb_path: Path, capsys):
        _write_entry(
            kb_path,
            "knowledge/topics/slop.md",
            _entry_markdown("Slop", "This uses load-bearing details."),
        )
        lint.main(["--path", str(kb_path), "--no-style"])
        out = json.loads(capsys.readouterr().out)
        assert _style_phrase_issues(out) == []
        assert out["style"]["findings"] == 0

    def test_cli_pattern_file(self, kb_path: Path, tmp_path: Path, capsys):
        patterns = tmp_path / "patterns.json"
        patterns.write_text(
            json.dumps(
                {
                    "schema": "kb-style-patterns/v1",
                    "flags": ["ignorecase"],
                    "patterns": [
                        {
                            "id": "custom",
                            "enabled": True,
                            "regex": "slopphrase",
                            "note": "custom phrase",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        _write_entry(
            kb_path,
            "knowledge/topics/slop.md",
            _entry_markdown("Slop", "This is slopphrase and load-bearing."),
        )
        lint.main(["--path", str(kb_path), "--patterns", str(patterns)])
        out = json.loads(capsys.readouterr().out)
        found = {issue["pattern"] for issue in _style_phrase_issues(out)}
        assert "custom" in found
        assert "load-bearing" in found

    def test_per_kb_disable_pattern(self, kb_path: Path):
        (kb_path / ".kb" / "style-patterns.json").write_text(
            json.dumps(
                {
                    "schema": "kb-style-patterns/v1",
                    "flags": ["ignorecase"],
                    "patterns": [
                        {
                            "id": "load-bearing",
                            "enabled": False,
                            "regex": r"load[- ]bearing",
                            "note": "disabled",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        _write_entry(
            kb_path,
            "knowledge/topics/slop.md",
            _entry_markdown("Slop", "This uses load-bearing details."),
        )
        result = lint.lint_kb(str(kb_path))
        assert _style_phrase_issues(result, pattern="load-bearing") == []
        assert "load-bearing" in result["style"]["disabled"]

    def test_malformed_exception_fails_loudly(self, kb_path: Path):
        exception_dir = kb_path / ".kb" / "style-exceptions"
        exception_dir.mkdir(parents=True, exist_ok=True)
        (exception_dir / "bad.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(lint.ContractViolationError):
            lint.lint_kb(str(kb_path))

    def test_cli_malformed_exception_exits_nonzero(self, kb_path: Path, capsys):
        exception_dir = kb_path / ".kb" / "style-exceptions"
        exception_dir.mkdir(parents=True, exist_ok=True)
        (exception_dir / "bad.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            lint.main(["--path", str(kb_path)])
        assert exc_info.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert "bad.json" in err["error"]

    def test_cli_non_utf8_pattern_file_exits_nonzero(self, kb_path: Path, tmp_path: Path, capsys):
        patterns = tmp_path / "bad-encoding.json"
        patterns.write_bytes(b'{"schema": "kb-style-patterns/v1", "patterns": [], "n": "\xff\xfe"}')
        with pytest.raises(SystemExit) as exc_info:
            lint.main(["--path", str(kb_path), "--patterns", str(patterns)])
        assert exc_info.value.code == 1
        assert "error" in json.loads(capsys.readouterr().err)

    def test_cli_malformed_pattern_file_exits_nonzero(self, kb_path: Path, tmp_path: Path, capsys):
        patterns = tmp_path / "broken.json"
        patterns.write_text('{"schema": "wrong/v1", "patterns": []}', encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            lint.main(["--path", str(kb_path), "--patterns", str(patterns)])
        assert exc_info.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert "kb-style-patterns/v1" in err["error"]
