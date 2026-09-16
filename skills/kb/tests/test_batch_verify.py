"""Tests for batch_verify.py — deterministic post-merge audit.

Covers the checks a main agent ran ad-hoc with python one-liners during
the e2e: log order, staged-completeness, index coverage, chain integrity,
staging-leakage, and tree hashing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ._loader import load_script_module

batch_plan = load_script_module("kb_test_verify_plan", "batch_plan.py")
batch_merge = load_script_module("kb_test_verify_merge", "batch_merge.py")
batch_verify = load_script_module("kb_test_verify", "batch_verify.py")
init = load_script_module("kb_test_verify_init", "init.py")


@pytest.fixture
def kb_path(tmp_path: Path) -> Path:
    p = tmp_path / "test-kb"
    init.scaffold_kb(str(p), "Test KB")
    return p


@pytest.fixture
def input_dir(tmp_path: Path) -> Path:
    d = tmp_path / "incoming"
    d.mkdir()
    (d / "alpha.md").write_text("# Alpha", encoding="utf-8")
    (d / "bravo.md").write_text("# Bravo", encoding="utf-8")
    return d


def _merged(kb_path: Path, input_dir: Path) -> dict:
    planned = batch_plan.plan_batch(
        str(kb_path), str(input_dir), "batch-v",
        state_dir=kb_path / ".kb" / "tasks",
    )
    src_ids = planned["source_ids"]
    bodies = [
        (
            "---\ntype: entity\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            f"source-ids: [{src_ids[0]}]\ntags: []\n---\n\n# Ada\n\n"
            "Ada studied [[topic-b]].\n"
        ),
        (
            "---\ntype: topic\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            f"source-ids: [{src_ids[1]}]\ntags: []\n---\n\n# Topic B\n\n"
            "[[ada|Ada]] pioneered computing.\n"
        ),
    ]
    rels = ["entities/ada.md", "topics/topic-b.md"]
    for sid, body, rel in zip(src_ids, bodies, rels):
        cf = kb_path / f"v-{sid}.md"
        cf.write_text(body, encoding="utf-8")
        batch_plan.stage_write(str(kb_path), "batch-v", sid, rel, str(cf))
    batch_merge.merge_batch(str(kb_path), "batch-v")
    return planned


class TestVerifyBatch:
    def test_happy_path_passes(self, kb_path: Path, input_dir: Path):
        planned = _merged(kb_path, input_dir)
        result = batch_verify.verify_batch(str(kb_path), "batch-v")
        assert result["status"] == "pass", json.dumps(result, indent=1)[:2000]
        assert result["checks"]["log_order"]["status"] == "pass"
        assert result["checks"]["completeness"]["status"] == "pass"
        assert result["checks"]["index"]["status"] == "pass"
        assert result["checks"]["chain"]["status"] == "pass"
        assert result["checks"]["leakage"]["status"] == "pass"
        report = kb_path / ".kb" / "batches" / "batch-v" / "verify-report.json"
        assert report.exists()  # retained audit artifact
        assert len(result["tree_hash"]) == 40

    def test_detects_log_reorder(self, kb_path: Path, input_dir: Path):
        planned = _merged(kb_path, input_dir)
        log = kb_path / "log.md"
        # Duplicate the first source's line at the end (simulates a crash
        # between write and cursor persist followed by a naive re-append).
        lines = log.read_text(encoding="utf-8").splitlines()
        first = next(
            line for line in lines if f"add {planned['source_ids'][0]}" in line
        )
        log.write_text("\n".join(lines + [first]) + "\n", encoding="utf-8")
        result = batch_verify.verify_batch(str(kb_path), "batch-v")
        assert result["checks"]["log_order"]["status"] == "fail"

    def test_detects_missing_live_file(self, kb_path: Path, input_dir: Path):
        _merged(kb_path, input_dir)
        (kb_path / "knowledge" / "topics" / "topic-b.md").unlink()
        result = batch_verify.verify_batch(str(kb_path), "batch-v")
        assert result["status"] == "fail"
        assert result["checks"]["completeness"]["status"] == "fail"

    def test_detects_missing_index_bullet(self, kb_path: Path, input_dir: Path):
        _merged(kb_path, input_dir)
        index = kb_path / "index.md"
        lines = [
            line
            for line in index.read_text(encoding="utf-8").splitlines()
            if "[[ada]]" not in line
        ]
        index.write_text("\n".join(lines) + "\n", encoding="utf-8")
        result = batch_verify.verify_batch(str(kb_path), "batch-v")
        assert result["checks"]["index"]["status"] == "fail"

    def test_detects_chain_break(self, kb_path: Path, input_dir: Path):
        _merged(kb_path, input_dir)
        years = kb_path / "knowledge" / "timeline" / "years"
        years.mkdir(parents=True, exist_ok=True)
        (years / "2020.md").write_text(
            "---\ntype: timeline\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            'source-ids: []\ntags: []\nnext: "[[2099]]"\n---\n\n# 2020\n',
            encoding="utf-8",
        )
        result = batch_verify.verify_batch(str(kb_path), "batch-v")
        assert result["checks"]["chain"]["status"] == "fail"

    def test_detects_staging_leakage(self, kb_path: Path, input_dir: Path):
        _merged(kb_path, input_dir)
        ada = kb_path / "knowledge" / "entities" / "ada.md"
        ada.write_text(
            ada.read_text(encoding="utf-8") + "\nSee staging/alpha-src/x.\n",
            encoding="utf-8",
        )
        result = batch_verify.verify_batch(str(kb_path), "batch-v")
        assert result["checks"]["leakage"]["status"] == "fail"

    def test_expect_hash(self, kb_path: Path, input_dir: Path):
        _merged(kb_path, input_dir)
        first = batch_verify.verify_batch(str(kb_path), "batch-v")
        same = batch_verify.verify_batch(
            str(kb_path), "batch-v", expect_hash=first["tree_hash"]
        )
        assert same["checks"]["hash"]["status"] == "pass"
        other = batch_verify.verify_batch(
            str(kb_path), "batch-v", expect_hash="0" * 40
        )
        assert other["checks"]["hash"]["status"] == "fail"

    def test_post_gc_skips_completeness(self, kb_path: Path, input_dir: Path):
        _merged(kb_path, input_dir)
        batch_merge.mark_done(str(kb_path), "batch-v")
        batch_merge.gc_batch(str(kb_path), "batch-v")
        result = batch_verify.verify_batch(str(kb_path), "batch-v")
        assert result["checks"]["completeness"]["status"] == "skipped"
        assert result["status"] == "pass"


class TestHygiene:
    def test_flags_double_h1(self, kb_path: Path, input_dir: Path):
        _merged(kb_path, input_dir)
        ada = kb_path / "knowledge" / "entities" / "ada.md"
        ada.write_text(
            ada.read_text(encoding="utf-8") + "\n# Ada Again\n\nMore.\n",
            encoding="utf-8",
        )
        result = batch_verify.verify_batch(str(kb_path), "batch-v")
        assert result["checks"]["hygiene"]["status"] == "warn"
        assert "top-level headings" in result["checks"]["hygiene"]["detail"]

    def test_flags_stale_batch_phrase(self, kb_path: Path, input_dir: Path):
        _merged(kb_path, input_dir)
        ada = kb_path / "knowledge" / "entities" / "ada.md"
        ada.write_text(
            ada.read_text(encoding="utf-8") + "\nSole source so far in this KB.\n",
            encoding="utf-8",
        )
        result = batch_verify.verify_batch(str(kb_path), "batch-v")
        assert result["checks"]["hygiene"]["status"] == "warn"

    def test_clean_files_pass(self, kb_path: Path, input_dir: Path):
        _merged(kb_path, input_dir)
        result = batch_verify.verify_batch(str(kb_path), "batch-v")
        assert result["checks"]["hygiene"]["status"] == "pass"
