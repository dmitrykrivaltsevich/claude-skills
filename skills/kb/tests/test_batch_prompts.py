"""Tests for batch_prompts.py — canned delegation prompts.

The e2e showed the main agent retyping worker/lint-fix prompts (with all
IDs, paths, and contract rules) on every run. Canned templates filled from
the manifest remove that toil and the copy-paste drift.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ._loader import load_script_module

batch_plan = load_script_module("kb_test_prompts_plan", "batch_plan.py")
batch_prompts = load_script_module("kb_test_prompts", "batch_prompts.py")
init = load_script_module("kb_test_prompts_init", "init.py")
ContractViolationError = batch_prompts.ContractViolationError


@pytest.fixture
def planned(tmp_path: Path) -> Path:
    kb = tmp_path / "test-kb"
    init.scaffold_kb(str(kb), "Test KB")
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "paper.md").write_text("# Paper", encoding="utf-8")
    batch_plan.plan_batch(
        str(kb), str(incoming), "batch-p",
        state_dir=kb / ".kb" / "tasks",
    )
    return kb


def _leftover_tokens(text: str) -> list[str]:
    # %%TOKENS%% must all be substituted; ${ENV} passthroughs are allowed.
    return sorted(set(re.findall(r"%%[A-Z_]+%%", text)))


class TestWorkerPrompt:
    def test_fills_all_fields(self, planned: Path):
        manifest_sid = batch_prompts.render_worker_prompt(
            str(planned), "batch-p", "paper-src"
        )
        assert "paper-src" in manifest_sid
        assert "--item-id i1" in manifest_sid or "i1" in manifest_sid
        assert "batch-p" in manifest_sid
        assert str(planned) in manifest_sid
        assert _leftover_tokens(manifest_sid) == []

    def test_names_source_file(self, planned: Path):
        text = batch_prompts.render_worker_prompt(
            str(planned), "batch-p", "paper-src"
        )
        assert "paper.md" in text  # input file discoverable from prompt alone

    def test_rejects_unknown_source(self, planned: Path):
        with pytest.raises(ContractViolationError, match="not part of batch"):
            batch_prompts.render_worker_prompt(
                str(planned), "batch-p", "nope-2020"
            )

    def test_states_contract(self, planned: Path):
        text = batch_prompts.render_worker_prompt(
            str(planned), "batch-p", "paper-src"
        )
        for must in ("stage-write", "rules-proposals.md", "handoff"):
            assert must in text


class TestLintfixPrompt:
    def test_renders(self, planned: Path):
        text = batch_prompts.render_lintfix_prompt(str(planned), "batch-p")
        assert "batch-p" in text
        assert str(planned) in text
        assert _leftover_tokens(text) == []
        assert "lint_fix.py" in text


class TestTriangulatePrompt:
    def test_renders(self, planned: Path):
        text = batch_prompts.render_triangulate_prompt(str(planned), "batch-p")
        assert "batch-p" in text
        assert str(planned) in text
        assert "paper-src" in text  # manifest source order listed
        assert _leftover_tokens(text) == []
        assert "merge-queue.json" in text


class TestWorkerTemplateContent:
    def _text(self, tmp_path):
        from ._loader import load_script_module as _load
        import pathlib
        kb = tmp_path / "kb-t"
        _load("kb_tmpl_init", "init.py").scaffold_kb(str(kb), "T")
        inc = tmp_path / "inc"
        inc.mkdir()
        (inc / "doc.md").write_text("# D", encoding="utf-8")
        bp = _load("kb_tmpl_plan", "batch_plan.py")
        bp.plan_batch(str(kb), str(inc), "b-t", state_dir=kb / ".kb" / "tasks")
        return kb

    def test_handoff_requires_timing(self, tmp_path):
        from ._loader import load_script_module as _load
        kb = self._text(tmp_path)
        pr = _load("kb_tmpl_pr", "batch_prompts.py")
        text = pr.render_worker_prompt(str(kb), "b-t", "doc-src")
        assert "started_at" in text and "finished_at" in text

    def test_rule_proposals_disambiguated(self, tmp_path):
        """Rule proposals are KB-curation conventions, never subject matter.

        Workers spend the whole run writing "Rule of thumb" idea sections,
        so an unqualified "rule ideas" line gets misfiled as domain
        heuristics. The template must disambiguate, frame the co-evolution
        target, and legitimize the empty outcome.
        """
        from ._loader import load_script_module as _load
        kb = self._text(tmp_path)
        pr = _load("kb_tmpl_pr3", "batch_prompts.py")
        text = pr.render_worker_prompt(str(kb), "b-t", "doc-src")
        assert "rules-coevolution.md" in text  # co-evolution frame
        assert "often zero" in text  # empty is a legitimate outcome
        assert "NEVER a claim" in text  # subject matter → ideas, never proposals
        assert "no KB-level conventions observed" in text

    def test_worker_checks_base_before_creating(self, tmp_path):
        """Later waves build on merged earlier waves: check base first.

        Recreating an existing concept wastes the merge and tokens; the
        template must demand search-before-stage, link-instead-of-recreate,
        and read-before-extend.
        """
        from ._loader import load_script_module as _load
        kb = self._text(tmp_path)
        pr = _load("kb_tmpl_pr4", "batch_prompts.py")
        text = pr.render_worker_prompt(str(kb), "b-t", "doc-src")
        assert "check-before-create" in text
        assert "link to it instead" in text
        assert "read it first" in text

    def test_routes_books_and_urls(self, tmp_path):
        from ._loader import load_script_module as _load
        kb = self._text(tmp_path)
        pr = _load("kb_tmpl_pr2", "batch_prompts.py")
        text = pr.render_worker_prompt(str(kb), "b-t", "doc-src")
        assert "50" in text  # large-source routing threshold present
        assert "chapter" in text.lower()
        assert "URL" in text or "url" in text
