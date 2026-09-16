"""Tests for lint_fix.py — mechanical lint repairs (backlinks, timeline).

Backlink and timeline-stub repairs are deterministic file operations, so
they belong in a script (run → re-lint → fixed), not in an agent loop.
Style-phrase findings stay agent-side (they need judgment).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ._loader import load_script_module

lint_fix = load_script_module("kb_test_lint_fix", "lint_fix.py")
init = load_script_module("kb_test_lint_fix_init", "init.py")


@pytest.fixture
def kb_path(tmp_path: Path) -> Path:
    p = tmp_path / "test-kb"
    init.scaffold_kb(str(p), "Test KB")
    return p


def _entry(title: str, body: str, source: str = "x-2020") -> str:
    return (
        "---\ntype: topic\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
        f"source-ids: [{source}]\ntags: []\n---\n\n# {title}\n\n{body}\n"
    )


def _year(stem: str) -> str:
    return (
        "---\ntype: timeline\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
        "source-ids: []\ntags: []\n---\n\n"
        f"# {stem}\n"
    )


class TestFixBacklinks:
    def _one_way(self, kb_path: Path) -> None:
        topics = kb_path / "knowledge" / "topics"
        (topics / "aaa.md").write_text(
            _entry("Aaa", "Links to [[bbb]]."), encoding="utf-8"
        )
        (topics / "bbb.md").write_text(
            _entry("Bbb", "No outgoing links."), encoding="utf-8"
        )

    def test_adds_reciprocal_link(self, kb_path: Path):
        self._one_way(kb_path)
        result = lint_fix.fix_backlinks(str(kb_path), apply=True)
        assert result["fixed"] == 1
        text = (kb_path / "knowledge" / "topics" / "bbb.md").read_text(
            encoding="utf-8"
        )
        assert "[[aaa]]" in text

    def test_dry_run_writes_nothing(self, kb_path: Path):
        self._one_way(kb_path)
        before = (kb_path / "knowledge" / "topics" / "bbb.md").read_bytes()
        result = lint_fix.fix_backlinks(str(kb_path), apply=False)
        assert result["fixed"] == 1  # would-fix count reported
        assert result["dry_run"] is True
        assert (kb_path / "knowledge" / "topics" / "bbb.md").read_bytes() == before

    def test_rerun_is_noop(self, kb_path: Path):
        self._one_way(kb_path)
        lint_fix.fix_backlinks(str(kb_path), apply=True)
        second = lint_fix.fix_backlinks(str(kb_path), apply=True)
        assert second["fixed"] == 0
        text = (kb_path / "knowledge" / "topics" / "bbb.md").read_text(
            encoding="utf-8"
        )
        assert text.count("[[aaa]]") == 1

    def test_creates_see_also_section(self, kb_path: Path):
        self._one_way(kb_path)
        lint_fix.fix_backlinks(str(kb_path), apply=True)
        text = (kb_path / "knowledge" / "topics" / "bbb.md").read_text(
            encoding="utf-8"
        )
        assert "## See also" in text

    def test_clean_kb_noop(self, kb_path: Path):
        result = lint_fix.fix_backlinks(str(kb_path), apply=True)
        assert result["fixed"] == 0


class TestFixTimeline:
    def _gap(self, kb_path: Path) -> None:
        years = kb_path / "knowledge" / "timeline" / "years"
        (years / "2020.md").write_text(_year("2020"), encoding="utf-8")
        (years / "2022.md").write_text(_year("2022"), encoding="utf-8")

    def test_creates_missing_year(self, kb_path: Path):
        self._gap(kb_path)
        result = lint_fix.fix_timeline(str(kb_path), apply=True)
        assert result["created"] == ["knowledge/timeline/years/2021.md"]
        assert (kb_path / "knowledge" / "timeline" / "years" / "2021.md").exists()

    def test_chain_consistent_after_fix(self, kb_path: Path):
        self._gap(kb_path)
        lint_fix.fix_timeline(str(kb_path), apply=True)
        t2020 = (kb_path / "knowledge" / "timeline" / "years" / "2020.md").read_text(
            encoding="utf-8"
        )
        t2021 = (kb_path / "knowledge" / "timeline" / "years" / "2021.md").read_text(
            encoding="utf-8"
        )
        t2022 = (kb_path / "knowledge" / "timeline" / "years" / "2022.md").read_text(
            encoding="utf-8"
        )
        assert "[[2021]]" in t2020  # next repaired, not left dangling
        assert "[[2020]]" in t2021 and "[[2022]]" in t2021
        assert "[[2021]]" in t2022

    def test_dry_run_writes_nothing(self, kb_path: Path, tmp_path: Path):
        self._gap(kb_path)
        before = sorted(
            p.stat().st_mtime_ns
            for p in (kb_path / "knowledge").rglob("*")
            if p.is_file()
        )
        result = lint_fix.fix_timeline(str(kb_path), apply=False)
        assert result["created"] == ["knowledge/timeline/years/2021.md"]
        assert result["dry_run"] is True
        after = sorted(
            p.stat().st_mtime_ns
            for p in (kb_path / "knowledge").rglob("*")
            if p.is_file()
        )
        assert before == after

    def test_rerun_is_noop(self, kb_path: Path):
        self._gap(kb_path)
        lint_fix.fix_timeline(str(kb_path), apply=True)
        second = lint_fix.fix_timeline(str(kb_path), apply=True)
        assert second["created"] == []

    def test_month_gap(self, kb_path: Path):
        months = kb_path / "knowledge" / "timeline" / "months"
        (months / "2020-01.md").write_text(_year("2020-01"), encoding="utf-8")
        (months / "2020-03.md").write_text(_year("2020-03"), encoding="utf-8")
        result = lint_fix.fix_timeline(str(kb_path), apply=True)
        assert "knowledge/timeline/months/2020-02.md" in result["created"]
        text = (months / "2020-02.md").read_text(encoding="utf-8")
        assert "[[2020-01]]" in text and "[[2020-03]]" in text
        assert "[[2020]]" in text  # parent year link


class TestTimelineChildSections:
    def test_year_stub_gains_months_section(self, kb_path: Path):
        months = kb_path / "knowledge" / "timeline" / "months"
        (months / "2020-01.md").write_text(
            "---\ntype: timeline\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            "source-ids: []\ntags: []\n---\n\n# 2020-01\n",
            encoding="utf-8",
        )
        years = kb_path / "knowledge" / "timeline" / "years"
        (years / "2020.md").write_text(
            "---\ntype: timeline\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            "source-ids: []\ntags: []\n---\n\n# 2020\n",
            encoding="utf-8",
        )
        result = lint_fix.fix_timeline(str(kb_path), apply=True)
        text = (years / "2020.md").read_text(encoding="utf-8")
        assert "## Months" in text
        assert "[[2020-01]]" in text

    def test_no_new_backlink_debt(self, kb_path: Path):
        months = kb_path / "knowledge" / "timeline" / "months"
        (months / "2020-01.md").write_text(
            "---\ntype: timeline\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            'source-ids: []\ntags: []\nparent: "[[2020]]"\n---\n\n# 2020-01\n',
            encoding="utf-8",
        )
        lint = load_script_module("kb_test_lint_fix_check", "lint.py")
        lint_fix.fix_timeline(str(kb_path), apply=True)
        remaining = [
            i for i in lint.lint_kb(str(kb_path), style_enabled=False)["issues"]
            if i["type"] == "missing-backlink"
            and "timeline" in i.get("file", "")
        ]
        assert remaining == []
