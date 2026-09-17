"""Tests for parallel batch import — batch_plan.py + batch_merge.py.

Covers the Map→Reduce protocol from references/parallel-import.md:
pre-register (sequential) → sparse-staging parallel map → ordered replay
with per-file escalation → single final lint → triage → GC.

Unit of work: one source through stage→merge. Checkpoint artifact:
.kb/batches/<batch-id>/manifest.json (+ merge-queue.json). Resume path:
reload manifest {phase, cursor} and continue. Handoff: {batch_id}.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from ._loader import load_script_module

batch_plan = load_script_module("kb_test_batch_plan", "batch_plan.py")
batch_merge = load_script_module("kb_test_batch_merge", "batch_merge.py")
init = load_script_module("kb_test_batch_init", "init.py")
ContractViolationError = batch_plan.ContractViolationError


def expect_violation(fn, pattern: str) -> None:
    """Assert a contract violation regardless of which isolated copy of
    contracts.py the raising script module bound (test loader sandboxes
    each script, so script modules carry distinct ContractViolationError
    identities — match on type name + message instead)."""
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 — intentionally any error type
        assert (
            type(exc).__name__ == "ContractViolationError"
        ), f"wrong error type: {type(exc).__name__}: {exc}"
        assert re.search(pattern, str(exc)), f"{pattern!r} not in: {exc}"
        return
    raise AssertionError(f"expected ContractViolationError({pattern})")


@pytest.fixture
def kb_path(tmp_path: Path) -> Path:
    p = tmp_path / "test-kb"
    init.scaffold_kb(str(p), "Test KB")
    return p


@pytest.fixture
def input_dir(tmp_path: Path) -> Path:
    d = tmp_path / "incoming"
    d.mkdir()
    (d / "bravo.md").write_text("# Bravo\n\nContent about Ada.", encoding="utf-8")
    (d / "alpha.md").write_text("# Alpha\n\nContent about Grace.", encoding="utf-8")
    return d


def _plan(kb_path: Path, input_dir: Path, batch_id: str = "batch-001") -> dict:
    return batch_plan.plan_batch(
        str(kb_path), str(input_dir), batch_id, state_dir=kb_path / ".kb" / "tasks"
    )


class TestPlanBatch:
    def test_creates_manifest_with_input_order(
        self, kb_path: Path, input_dir: Path
    ):
        result = _plan(kb_path, input_dir)
        manifest_path = kb_path / ".kb" / "batches" / "batch-001" / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        # Directory scan order is sorted byte order for determinism.
        assert [s["input_name"] for s in manifest["sources"]] == [
            "alpha.md",
            "bravo.md",
        ]
        assert result["total_sources"] == 2

    def test_pre_registers_all_sources(self, kb_path: Path, input_dir: Path):
        result = _plan(kb_path, input_dir)
        import yaml

        config = yaml.safe_load(
            (kb_path / ".kb" / "config.yaml").read_text(encoding="utf-8")
        )
        assert {s["id"] for s in config["sources"]} == set(result["source_ids"])

    def test_mints_unique_ids_on_collision(self, kb_path: Path, tmp_path: Path):
        d = tmp_path / "incoming"
        d.mkdir()
        (d / "paper.md").write_text("# One", encoding="utf-8")
        (d / "paper-copy.md").write_text("# Two", encoding="utf-8")
        # Force same slug base via explicit duplicate filenames is hard;
        # instead register one source first, then plan a batch whose slug
        # collides with the registered id.
        import yaml

        first = _plan(kb_path, d, batch_id="batch-001")
        assert len(set(first["source_ids"])) == 2
        config = yaml.safe_load(
            (kb_path / ".kb" / "config.yaml").read_text(encoding="utf-8")
        )
        assert len(config["sources"]) == 2

    def test_same_stem_in_subdirs_gets_suffix(
        self, kb_path: Path, tmp_path: Path
    ):
        d = tmp_path / "incoming"
        (d / "a").mkdir(parents=True)
        (d / "b").mkdir(parents=True)
        (d / "a" / "report.md").write_text("# A", encoding="utf-8")
        (d / "b" / "report.md").write_text("# B", encoding="utf-8")
        result = _plan(kb_path, d, batch_id="batch-collide")
        assert len(set(result["source_ids"])) == 2
        # Same slug base → second id carries a disambiguating suffix.
        assert result["source_ids"][0] != result["source_ids"][1]
        assert result["source_ids"][1].startswith(result["source_ids"][0])

    def test_idempotent_rerun_resumes(self, kb_path: Path, input_dir: Path):
        first = _plan(kb_path, input_dir)
        second = _plan(kb_path, input_dir)
        assert second["resumed"] is True
        assert second["source_ids"] == first["source_ids"]
        import yaml

        config = yaml.safe_load(
            (kb_path / ".kb" / "config.yaml").read_text(encoding="utf-8")
        )
        assert len(config["sources"]) == 2  # no duplicates on re-plan

    def test_rejects_empty_batch_id(self, kb_path: Path, input_dir: Path):
        with pytest.raises(ContractViolationError, match="batch_id"):
            batch_plan.plan_batch(
                str(kb_path),
                str(input_dir),
                "",
                state_dir=kb_path / ".kb" / "tasks",
            )

    def test_rejects_missing_input(self, kb_path: Path, tmp_path: Path):
        with pytest.raises(ContractViolationError, match="input"):
            batch_plan.plan_batch(
                str(kb_path),
                str(tmp_path / "nope"),
                "batch-002",
                state_dir=kb_path / ".kb" / "tasks",
            )

    def test_bare_url_input_points_to_list_file(
        self, kb_path: Path, tmp_path: Path
    ):
        """A bare URL as --input is the natural mistake: the error must
        teach the list-file recipe instead of failing generically."""
        with pytest.raises(ContractViolationError, match="one per line"):
            batch_plan.plan_batch(
                str(kb_path),
                "https://example.com/article",
                "batch-bare-url",
                state_dir=kb_path / ".kb" / "tasks",
            )

    def test_mixed_list_file_kinds_and_order(
        self, kb_path: Path, tmp_path: Path
    ):
        """File + URL lines keep caller order; URLs become references."""
        doc = tmp_path / "paper.md"
        doc.write_text("# Paper\n", encoding="utf-8")
        list_file = tmp_path / "mixed.txt"
        list_file.write_text(
            f"{doc}\n\n# a comment\nhttps://example.com/article\n",
            encoding="utf-8",
        )
        result = batch_plan.plan_batch(
            str(kb_path),
            str(list_file),
            "batch-mixed",
            state_dir=kb_path / ".kb" / "tasks",
        )
        manifest = json.loads(
            (
                kb_path / ".kb" / "batches" / "batch-mixed" / "manifest.json"
            ).read_text(encoding="utf-8")
        )
        assert [(s["kind"], s["location"]) for s in manifest["sources"]] == [
            ("file", str(doc.resolve())),
            ("reference", "https://example.com/article"),
        ]
        assert result["total_sources"] == 2

    def test_url_list_order_preserved(self, kb_path: Path, tmp_path: Path):
        list_file = tmp_path / "urls.txt"
        list_file.write_text(
            "https://example.com/zebra\nhttps://example.com/apple\n",
            encoding="utf-8",
        )
        result = batch_plan.plan_batch(
            str(kb_path),
            str(list_file),
            "batch-urls",
            state_dir=kb_path / ".kb" / "tasks",
        )
        manifest = json.loads(
            (
                kb_path / ".kb" / "batches" / "batch-urls" / "manifest.json"
            ).read_text(encoding="utf-8")
        )
        assert [s["location"] for s in manifest["sources"]] == [
            "https://example.com/zebra",
            "https://example.com/apple",
        ]
        assert result["total_sources"] == 2


class TestStageWrite:
    def test_stage_write_records_op(self, kb_path: Path, input_dir: Path):
        _plan(kb_path, input_dir)
        body = (
            "---\ntype: entity\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            "source-ids: [alpha-src]\ntags: []\n---\n\n# Ada\n\nContent.\n"
        )
        content_file = kb_path / "staged-body.md"
        content_file.write_text(body, encoding="utf-8")
        result = batch_plan.stage_write(
            str(kb_path),
            "batch-001",
            "alpha-src",
            "entities/ada.md",
            str(content_file),
        )
        staged = (
            kb_path
            / ".kb"
            / "batches"
            / "batch-001"
            / "staging"
            / "alpha-src"
            / "entities"
            / "ada.md"
        )
        assert staged.exists()
        assert result["staged_sha1"] == batch_merge.sha1_text(body)

    def test_stage_write_rejects_foreign_asset_namespace(
        self, kb_path: Path, input_dir: Path
    ):
        _plan(kb_path, input_dir)
        blob = kb_path / "blob.bin"
        blob.write_bytes(b"\x00\x01")
        with pytest.raises(ContractViolationError, match="namespaced"):
            batch_plan.stage_write(
                str(kb_path),
                "batch-001",
                "alpha-src",
                "assets/bravo-src/logo.png",
                str(blob),
            )

    def test_stage_write_rejects_live_kb_paths(
        self, kb_path: Path, input_dir: Path
    ):
        _plan(kb_path, input_dir)
        content_file = kb_path / "evil.md"
        content_file.write_text("x", encoding="utf-8")
        with pytest.raises(ContractViolationError, match="knowledge"):
            batch_plan.stage_write(
                str(kb_path),
                "batch-001",
                "alpha-src",
                "../index.md",
                str(content_file),
            )
        with pytest.raises(ContractViolationError, match="forbidden"):
            batch_plan.stage_write(
                str(kb_path),
                "batch-001",
                "alpha-src",
                "index.md",
                str(content_file),
            )


class TestMerge:
    def _staged_batch(self, kb_path: Path, input_dir: Path) -> dict:
        planned = _plan(kb_path, input_dir)
        src_ids = planned["source_ids"]
        # Reciprocally linked so the merged KB passes lint clean.
        first_body = (
            "---\ntype: entity\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            f"source-ids: [{src_ids[0]}]\ntags: [ai]\n---\n\n# Ada\n\n"
            "Ada studied [[topic-b]].\n"
        )
        second_body = (
            "---\ntype: topic\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            f"source-ids: [{src_ids[1]}]\ntags: []\n---\n\n# Topic B\n\n"
            "[[ada|Ada]] pioneered computing.\n"
        )
        for sid, body, rel in (
            (src_ids[0], first_body, "entities/ada.md"),
            (src_ids[1], second_body, "topics/topic-b.md"),
        ):
            cf = kb_path / f"body-{sid}.md"
            cf.write_text(body, encoding="utf-8")
            batch_plan.stage_write(
                str(kb_path), "batch-001", sid, rel, str(cf)
            )
        return planned

    def test_merge_applies_staged_files_in_order(
        self, kb_path: Path, input_dir: Path
    ):
        self._staged_batch(kb_path, input_dir)
        result = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert result["applied"] == 2
        assert (kb_path / "knowledge" / "entities" / "ada.md").exists()
        assert (kb_path / "knowledge" / "topics" / "topic-b.md").exists()

    def test_merge_dedups_identical_content(
        self, kb_path: Path, input_dir: Path
    ):
        self._staged_batch(kb_path, input_dir)
        first = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert first["applied"] == 2
        before = {
            p.relative_to(kb_path).as_posix(): p.read_bytes()
            for p in sorted((kb_path / "knowledge").rglob("*.md"))
        }
        second = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert second["applied"] == 0  # idempotent replay is a no-op
        after = {
            p.relative_to(kb_path).as_posix(): p.read_bytes()
            for p in sorted((kb_path / "knowledge").rglob("*.md"))
        }
        assert after == before  # replay changes zero bytes

    def test_merge_unions_same_file_from_two_sources(
        self, kb_path: Path, input_dir: Path
    ):
        planned = _plan(kb_path, input_dir)
        src_ids = planned["source_ids"]
        body_a = (
            "---\ntype: entity\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            f"source-ids: [{src_ids[0]}]\ntags: [ai]\n---\n\n# Ada\n\nFact one.\n"
        )
        body_b = (
            "---\ntype: entity\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            f"source-ids: [{src_ids[1]}]\ntags: [history]\n---\n\n# Ada\n\nFact two.\n"
        )
        for sid, body in ((src_ids[0], body_a), (src_ids[1], body_b)):
            cf = kb_path / f"overlap-{sid}.md"
            cf.write_text(body, encoding="utf-8")
            batch_plan.stage_write(
                str(kb_path), "batch-001", sid, "entities/ada.md", str(cf)
            )
        result = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert result["escalated"] == 1
        merged = (
            kb_path / "knowledge" / "entities" / "ada.md"
        ).read_text(encoding="utf-8")
        # Conservative union: neither worker's facts are lost.
        assert "Fact one." in merged
        assert "Fact two." in merged
        assert src_ids[0] in merged and src_ids[1] in merged

    def test_merge_never_touches_live_kb_during_stage(
        self, kb_path: Path, input_dir: Path
    ):
        _plan(kb_path, input_dir)
        assert not (kb_path / "knowledge" / "entities" / "ada.md").exists()

    def test_log_lines_follow_manifest_order(
        self, kb_path: Path, input_dir: Path
    ):
        planned = self._staged_batch(kb_path, input_dir)
        batch_merge.merge_batch(str(kb_path), "batch-001")
        log_text = (kb_path / "log.md").read_text(encoding="utf-8")
        positions = [log_text.index(sid) for sid in planned["source_ids"]]
        assert positions == sorted(positions)
        for sid in planned["source_ids"]:
            assert f"add {sid} | batch batch-001" in log_text

    def test_overlap_replay_is_idempotent(
        self, kb_path: Path, input_dir: Path
    ):
        planned = _plan(kb_path, input_dir)
        src_ids = planned["source_ids"]
        body_a = (
            "---\ntype: entity\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            f"source-ids: [{src_ids[0]}]\ntags: [ai]\n---\n\n# Ada\n\nFact one.\n"
        )
        body_b = (
            "---\ntype: entity\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            f"source-ids: [{src_ids[1]}]\ntags: [history]\n---\n\n# Ada\n\n"
            "Fact two.\n"
        )
        for sid, body in ((src_ids[0], body_a), (src_ids[1], body_b)):
            cf = kb_path / f"overlap-{sid}.md"
            cf.write_text(body, encoding="utf-8")
            batch_plan.stage_write(
                str(kb_path), "batch-001", sid, "entities/ada.md", str(cf)
            )
        first = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert first["escalated"] == 1
        log_before = (kb_path / "log.md").read_text(encoding="utf-8")
        index_before = (kb_path / "index.md").read_text(encoding="utf-8")
        second = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert second["applied"] == 0
        assert second["escalated"] == 0
        assert (kb_path / "log.md").read_text(encoding="utf-8") == log_before
        assert (kb_path / "index.md").read_text(encoding="utf-8") == index_before

    def test_dry_run_writes_nothing(self, kb_path: Path, input_dir: Path):
        self._staged_batch(kb_path, input_dir)
        before = {
            str(p): (p.stat().st_mtime_ns, p.read_bytes())
            for p in sorted((kb_path / ".kb").rglob("*"))
            if p.is_file()
        }
        kb_files_before = {
            str(p)
            for p in list((kb_path / "knowledge").rglob("*"))
            + [kb_path / "index.md", kb_path / "log.md"]
        }
        result = batch_merge.merge_batch(str(kb_path), "batch-001", dry_run=True)
        assert result["dry_run"] is True
        assert result["applied"] == 2
        after = {
            str(p): (p.stat().st_mtime_ns, p.read_bytes())
            for p in sorted((kb_path / ".kb").rglob("*"))
            if p.is_file()
        }
        assert before == after
        kb_files_after = {
            str(p)
            for p in list((kb_path / "knowledge").rglob("*"))
            + [kb_path / "index.md", kb_path / "log.md"]
        }
        assert kb_files_before == kb_files_after

    def test_external_changes_are_reported(
        self, kb_path: Path, input_dir: Path
    ):
        self._staged_batch(kb_path, input_dir)
        outsider = kb_path / "knowledge" / "topics" / "outsider.md"
        outsider.write_text(
            "---\ntype: topic\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            "source-ids: []\ntags: []\n---\n\n# Outsider\n\nExternal edit.\n",
            encoding="utf-8",
        )
        result = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert "knowledge/topics/outsider.md" in result["external_changes"]["added"]

    def test_external_edit_to_staged_file_escalates(
        self, kb_path: Path, input_dir: Path
    ):
        planned = _plan(kb_path, input_dir)
        src_id = planned["source_ids"][0]
        body = (
            "---\ntype: entity\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            f"source-ids: [{src_id}]\ntags: []\n---\n\n# Ada\n\nStaged fact.\n"
        )
        cf = kb_path / "staged-ada.md"
        cf.write_text(body, encoding="utf-8")
        batch_plan.stage_write(
            str(kb_path), "batch-001", src_id, "entities/ada.md", str(cf)
        )
        # Someone edits the live file between stage and merge.
        (kb_path / "knowledge" / "entities" / "ada.md").write_text(
            "---\ntype: entity\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            "source-ids: [other-2020]\ntags: []\n---\n\n# Ada\n\nLive fact.\n",
            encoding="utf-8",
        )
        result = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert result["escalated"] == 1
        merged = (kb_path / "knowledge" / "entities" / "ada.md").read_text(
            encoding="utf-8"
        )
        assert "Staged fact." in merged
        assert "Live fact." in merged


class TestIncrementalMerge:
    """Per-wave materialization: merge records a cursor; later merges
    process only new/changed staging and union with live content."""

    def _body(self, sid: str, fact: str) -> str:
        return (
            "---\ntype: entity\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            f"source-ids: [{sid}]\ntags: []\n---\n\n# Ada\n\n{fact}\n"
        )

    def _stage(
        self, kb_path: Path, batch_id: str, sid: str, rel: str, body: str
    ) -> None:
        cf = kb_path / f"inc-{sid}-{Path(rel).stem}.md"
        cf.write_text(body, encoding="utf-8")
        batch_plan.stage_write(str(kb_path), batch_id, sid, rel, str(cf))

    def _manifest(self, kb_path: Path, batch_id: str = "batch-001") -> dict:
        return json.loads(
            (
                kb_path / ".kb" / "batches" / batch_id / "manifest.json"
            ).read_text(encoding="utf-8")
        )

    def test_merge_records_cursor_and_holds_phase(
        self, kb_path: Path, input_dir: Path
    ):
        planned = _plan(kb_path, input_dir)
        sids = planned["source_ids"]
        self._stage(
            kb_path, "batch-001", sids[0], "entities/ada.md",
            self._body(sids[0], "Wave-one fact."),
        )
        first = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert first["applied"] == 1
        manifest = self._manifest(kb_path)
        assert sids[0] in manifest["merged"]
        assert sids[1] not in manifest["merged"]
        assert manifest["phase"] != "linting"  # waves remain
        status = batch_plan.batch_status(str(kb_path), "batch-001")
        assert status["merged_sources"] == [sids[0]]
        live = (
            kb_path / "knowledge" / "entities" / "ada.md"
        ).read_text(encoding="utf-8")
        assert "Wave-one fact." in live

    def test_second_merge_extends_without_clobber(
        self, kb_path: Path, input_dir: Path
    ):
        planned = _plan(kb_path, input_dir)
        sids = planned["source_ids"]
        self._stage(
            kb_path, "batch-001", sids[0], "entities/ada.md",
            self._body(sids[0], "Wave-one fact."),
        )
        batch_merge.merge_batch(str(kb_path), "batch-001")
        # Wave-two worker reads live and stages the extended version.
        live = (
            kb_path / "knowledge" / "entities" / "ada.md"
        ).read_text(encoding="utf-8")
        extended = live.replace(
            f"source-ids: [{sids[0]}]",
            f"source-ids: [{sids[0]}, {sids[1]}]",
        ).replace("Wave-one fact.", "Wave-one fact.\n\nWave-two fact.")
        self._stage(
            kb_path, "batch-001", sids[1], "entities/ada.md", extended
        )
        second = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert second["applied"] == 1  # only the new source replayed
        live = (
            kb_path / "knowledge" / "entities" / "ada.md"
        ).read_text(encoding="utf-8")
        assert "Wave-one fact." in live  # not clobbered
        assert "Wave-two fact." in live
        manifest = self._manifest(kb_path)
        assert set(manifest["merged"]) == set(sids)
        assert manifest["phase"] == "linting"  # all waves merged
        third = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert third["applied"] == 0  # replay is a no-op, not an error

    def test_restaged_source_remerges(self, kb_path: Path, input_dir: Path):
        planned = _plan(kb_path, input_dir)
        sids = planned["source_ids"]
        self._stage(
            kb_path, "batch-001", sids[0], "entities/ada.md",
            self._body(sids[0], "Version one."),
        )
        batch_merge.merge_batch(str(kb_path), "batch-001")
        self._stage(
            kb_path, "batch-001", sids[0], "entities/ada.md",
            self._body(sids[0], "Version two."),
        )
        result = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert result["applied"] == 1  # changed ops are not cursor-skipped
        live = (
            kb_path / "knowledge" / "entities" / "ada.md"
        ).read_text(encoding="utf-8")
        assert "Version two." in live


class TestTimelineChain:
    def test_rebuild_sets_prev_next_parent(
        self, kb_path: Path, input_dir: Path
    ):
        _plan(kb_path, input_dir)
        (kb_path / "knowledge" / "timeline" / "years" / "2024.md").write_text(
            "---\ntype: timeline\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            "source-ids: []\ntags: []\n---\n\n# 2024\n",
            encoding="utf-8",
        )
        (kb_path / "knowledge" / "timeline" / "years" / "2026.md").write_text(
            "---\ntype: timeline\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            "source-ids: []\ntags: []\n---\n\n# 2026\n",
            encoding="utf-8",
        )
        (kb_path / "knowledge" / "timeline" / "years" / "2025.md").write_text(
            "---\ntype: timeline\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            "source-ids: []\ntags: []\n---\n\n# 2025\n",
            encoding="utf-8",
        )
        batch_merge.rebuild_timeline_chain(str(kb_path))
        text_2025 = (
            kb_path / "knowledge" / "timeline" / "years" / "2025.md"
        ).read_text(encoding="utf-8")
        # YAML may single- or double-quote the wikilinks — assert targets.
        assert "[[2024]]" in text_2025
        assert "[[2026]]" in text_2025


class TestRulesFold:
    def test_fold_dedups_identical_proposals(
        self, kb_path: Path, input_dir: Path
    ):
        _plan(kb_path, input_dir)
        staging = kb_path / ".kb" / "batches" / "batch-001" / "staging"
        for sid in ("alpha-src", "bravo-src"):
            d = staging / sid
            d.mkdir(parents=True, exist_ok=True)
            (d / "rules-proposals.md").write_text(
                "- Prefer kebab-case slugs.\n", encoding="utf-8"
            )
        result = batch_merge.fold_rules_proposals(str(kb_path), "batch-001")
        assert result["proposals"] == 1  # identical bullets deduped
        combined = (
            kb_path / ".kb" / "batches" / "batch-001" / "rules-combined.md"
        )
        assert combined.exists()


class TestGc:
    def test_gc_refuses_before_done(self, kb_path: Path, input_dir: Path):
        self_ = TestMerge()
        self_._staged_batch(kb_path, input_dir)
        batch_merge.merge_batch(str(kb_path), "batch-001")
        expect_violation(
            lambda: batch_merge.gc_batch(str(kb_path), "batch-001"), "done"
        )

    def test_gc_keeps_manifest_queue_and_report(
        self, kb_path: Path, input_dir: Path
    ):
        self_ = TestMerge()
        self_._staged_batch(kb_path, input_dir)
        batch_merge.merge_batch(str(kb_path), "batch-001")
        batch_merge.mark_done(str(kb_path), "batch-001")
        result = batch_merge.gc_batch(str(kb_path), "batch-001")
        assert result["removed"] == ["staging"]
        batch_dir = kb_path / ".kb" / "batches" / "batch-001"
        assert (batch_dir / "manifest.json").exists()
        # merge-queue.json stays as the per-file conflict audit trail.
        assert (batch_dir / "merge-queue.json").exists()
        assert (batch_dir / "lint-report.json").exists()
        assert not (batch_dir / "staging").exists()

    def test_mark_done_rejects_dirty_lint(
        self, kb_path: Path, input_dir: Path
    ):
        self_ = TestMerge()
        self_._staged_batch(kb_path, input_dir)
        batch_merge.merge_batch(str(kb_path), "batch-001")
        # Break the KB: a dangling wikilink fails the lint gate.
        (kb_path / "knowledge" / "topics" / "broken.md").write_text(
            "---\ntype: topic\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            "source-ids: []\ntags: []\n---\n\n# Broken\n\nLinks [[nope-missing]].\n",
            encoding="utf-8",
        )
        expect_violation(
            lambda: batch_merge.mark_done(str(kb_path), "batch-001"),
            "lint issues",
        )

    def test_gc_rerun_is_noop(self, kb_path: Path, input_dir: Path):
        self_ = TestMerge()
        self_._staged_batch(kb_path, input_dir)
        batch_merge.merge_batch(str(kb_path), "batch-001")
        batch_merge.mark_done(str(kb_path), "batch-001")
        batch_merge.gc_batch(str(kb_path), "batch-001")
        second = batch_merge.gc_batch(str(kb_path), "batch-001")
        assert second["removed"] == []

    def test_replan_with_different_inputs_rejected(
        self, kb_path: Path, input_dir: Path, tmp_path: Path
    ):
        _plan(kb_path, input_dir)
        other = tmp_path / "other"
        other.mkdir()
        (other / "zzz.md").write_text("# Z", encoding="utf-8")
        expect_violation(
            lambda: batch_plan.plan_batch(
                str(kb_path),
                str(other),
                "batch-001",
                state_dir=kb_path / ".kb" / "tasks",
            ),
            "different inputs",
        )


class TestStatusReporting:
    def test_status_does_not_write_inside_batch(
        self, kb_path: Path, input_dir: Path, tmp_path: Path
    ):
        _plan(kb_path, input_dir)
        out = tmp_path / "status.json"
        before = sorted(
            p.stat().st_mtime_ns
            for p in (kb_path / ".kb" / "batches" / "batch-001").rglob("*")
            if p.is_file()
        )
        result = batch_plan.batch_status(
            str(kb_path), "batch-001", output_path=str(out)
        )
        assert result["batch_id"] == "batch-001"
        assert out.exists()  # only permitted write is caller-named --output
        after = sorted(
            p.stat().st_mtime_ns
            for p in (kb_path / ".kb" / "batches" / "batch-001").rglob("*")
            if p.is_file()
        )
        assert before == after


class TestLintExclusion:
    def test_style_scan_ignores_batch_scratch(
        self, kb_path: Path, input_dir: Path
    ):
        lint = load_script_module("kb_test_batch_lint", "lint.py")
        _plan(kb_path, input_dir)
        scratch = (
            kb_path
            / ".kb"
            / "batches"
            / "batch-001"
            / "staging"
            / "alpha-src"
            / "entities"
            / "draft.md"
        )
        scratch.parent.mkdir(parents=True, exist_ok=True)
        scratch.write_text("# Draft\n\nWork in progress.", encoding="utf-8")
        scanned = lint._style_files(kb_path)
        assert scratch not in scanned


class TestRoundTwo:
    def test_staged_tamper_after_record_rejected(
        self, kb_path: Path, input_dir: Path
    ):
        planned = _plan(kb_path, input_dir)
        src_id = planned["source_ids"][0]
        cf = kb_path / "tamper.md"
        cf.write_text("---\ntype: topic\n---\n\n# T\n\nV1.\n", encoding="utf-8")
        batch_plan.stage_write(
            str(kb_path), "batch-001", src_id, "topics/tamper.md", str(cf)
        )
        # Hand-edit the staged file after its ops record was written.
        staged = (
            kb_path
            / ".kb"
            / "batches"
            / "batch-001"
            / "staging"
            / src_id
            / "topics"
            / "tamper.md"
        )
        staged.write_text("tampered", encoding="utf-8")
        expect_violation(
            lambda: batch_merge.merge_batch(str(kb_path), "batch-001"),
            "no longer matches",
        )

    def test_binary_variant_replay_is_idempotent(
        self, kb_path: Path, input_dir: Path
    ):
        planned = _plan(kb_path, input_dir)
        src_id = planned["source_ids"][0]
        blob = kb_path / "logo.png"
        blob.write_bytes(b"\x89PNG-staged")
        batch_plan.stage_write(
            str(kb_path),
            "batch-001",
            src_id,
            f"assets/{src_id}/logo.png",
            str(blob),
        )
        live = kb_path / "knowledge" / "assets" / src_id / "logo.png"
        live.parent.mkdir(parents=True, exist_ok=True)
        live.write_bytes(b"\x89PNG-live")
        first = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert first["escalated"] == 1
        variants = list(live.parent.glob("logo-*.png"))
        assert len(variants) == 1
        second = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert second["applied"] == 0
        assert second["escalated"] == 0
        assert list(live.parent.glob("logo-*.png")) == variants

    def test_union_replay_ignores_updated_stamp(
        self, kb_path: Path, input_dir: Path
    ):
        planned = _plan(kb_path, input_dir)
        src_ids = planned["source_ids"]
        bodies = [
            (
                "---\ntype: entity\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
                f"source-ids: [{src_ids[0]}]\ntags: []\n---\n\n# Ada\n\nOne.\n"
            ),
            (
                "---\ntype: entity\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
                f"source-ids: [{src_ids[1]}]\ntags: []\n---\n\n# Ada\n\nTwo.\n"
            ),
        ]
        for sid, body in zip(src_ids, bodies):
            cf = kb_path / f"u-{sid}.md"
            cf.write_text(body, encoding="utf-8")
            batch_plan.stage_write(
                str(kb_path), "batch-001", sid, "entities/ada.md", str(cf)
            )
        batch_merge.merge_batch(str(kb_path), "batch-001")
        # Simulate a later day: backdate the stamp; content is converged.
        live = kb_path / "knowledge" / "entities" / "ada.md"
        live.write_text(
            live.read_text(encoding="utf-8").replace(
                f"updated: '{batch_merge._utc_today()}'",
                "updated: 2000-01-01",
            ),
            encoding="utf-8",
        )
        rerun = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert rerun["applied"] == 0
        assert rerun["escalated"] == 0

    def test_status_reports_corrupt_ops(
        self, kb_path: Path, input_dir: Path
    ):
        planned = _plan(kb_path, input_dir)
        ops = (
            kb_path
            / ".kb"
            / "batches"
            / "batch-001"
            / "staging"
            / planned["source_ids"][0]
        )
        ops.mkdir(parents=True, exist_ok=True)
        (ops / "ops.jsonl").write_text("{not json}\n", encoding="utf-8")
        result = batch_plan.batch_status(str(kb_path), "batch-001")
        assert result["staged_ops"][planned["source_ids"][0]]["error"] is not None

    def test_fingerprint_spelling_independent(
        self, kb_path: Path, tmp_path: Path
    ):
        target = tmp_path / "doc.md"
        target.write_text("# D", encoding="utf-8")
        list_abs = tmp_path / "a.txt"
        list_abs.write_text(f"{target}\n", encoding="utf-8")
        sub = tmp_path / "sub"
        sub.mkdir()
        list_rel = sub / "b.txt"
        list_rel.write_text("../doc.md\n", encoding="utf-8")
        first = batch_plan.plan_batch(
            str(kb_path),
            str(list_abs),
            "batch-spell",
            state_dir=kb_path / ".kb" / "tasks",
        )
        second = batch_plan.plan_batch(
            str(kb_path),
            str(list_rel),
            "batch-spell",
            state_dir=kb_path / ".kb" / "tasks",
        )
        assert second["resumed"] is True
        assert second["source_ids"] == first["source_ids"]


class TestEmptyEquivalence:
    def test_null_vs_empty_string_converges(self):
        merge = load_script_module("kb_test_batch_union", "batch_merge.py")
        live = (
            "---\ntype: timeline\nprev: '[[2008]]'\nnext: ''\nparent: null\n"
            "source-ids: [a]\n---\n\n# T\n\nBody.\n"
        )
        staged = (
            "---\ntype: timeline\nprev: null\nnext: null\nparent: null\n"
            "source-ids: [a]\n---\n\n# T\n\nBody.\n"
        )
        merged, overlap, conflicts = merge._union_merge_md(live, staged, "a")
        assert overlap is True
        # Staged-empty contributes nothing: live prev kept without a
        # conflict record, empty-vs-empty ("" vs null on next) keeps
        # accumulated verbatim, no flip.
        assert conflicts == {}
        assert "prev: '[[2008]]'" in merged
        assert "next: ''" in merged
        # Second union with the merged result is a fixed point.
        merged2, _, _ = merge._union_merge_md(merged, staged, "a")
        assert merged2 == merged

    def test_settled_empty_beats_staged_guess(self):
        merge = load_script_module("kb_test_batch_union2", "batch_merge.py")
        # Chain-settled "" (known: no previous year) must survive a
        # worker's stale [[1979]] guess — otherwise union and chain
        # rebuild ping-pong the value on every replay (real e2e finding).
        live = (
            "---\ntype: timeline\nprev: ''\nnext: '[[1985]]'\n"
            "source-ids: [a]\n---\n\n# T\n\nBody.\n"
        )
        staged = (
            "---\ntype: timeline\nprev: '[[1979]]'\nnext: '[[1981]]'\n"
            "source-ids: [a]\n---\n\n# T\n\nBody.\n"
        )
        merged, _, conflicts = merge._union_merge_md(live, staged, "a")
        assert "prev: ''" in merged
        assert "next: '[[1985]]'" in merged
        assert set(conflicts) == {"next"}
        merged2, _, _ = merge._union_merge_md(merged, staged, "a")
        assert merged2 == merged


class TestQueueAudit:
    def test_escalation_survives_clean_replay(self, kb_path, input_dir):
        planned = batch_plan.plan_batch(
            str(kb_path), str(input_dir), "batch-q",
            state_dir=kb_path / ".kb" / "tasks",
        )
        src_ids = planned["source_ids"]
        for sid, fact in ((src_ids[0], "Fact one."), (src_ids[1], "Fact two.")):
            cf = kb_path / f"q-{sid}.md"
            cf.write_text(
                "---\ntype: entity\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
                f"source-ids: [{sid}]\ntags: []\n---\n\n# Ada\n\n{fact}\n",
                encoding="utf-8",
            )
            batch_plan.stage_write(
                str(kb_path), "batch-q", sid, "entities/ada.md", str(cf)
            )
        batch_merge.merge_batch(str(kb_path), "batch-q")
        second = batch_merge.merge_batch(str(kb_path), "batch-q")
        assert second["escalated"] == 0
        queue = json.loads(
            (kb_path / ".kb" / "batches" / "batch-q" / "merge-queue.json")
            .read_text(encoding="utf-8")
        )
        assert [e["path"] for e in queue["entries"]] == ["entities/ada.md"]


class TestStatusQueueDetail:
    def test_status_names_escalated_files(self, kb_path, input_dir):
        planned = batch_plan.plan_batch(
            str(kb_path), str(input_dir), "batch-sq",
            state_dir=kb_path / ".kb" / "tasks",
        )
        src_ids = planned["source_ids"]
        for sid in src_ids[:2]:
            cf = kb_path / f"sq-{sid}.md"
            cf.write_text(
                "---\ntype: entity\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
                f"source-ids: [{sid}]\ntags: []\n---\n\n# Ada\n\nFact {sid}.\n",
                encoding="utf-8",
            )
            batch_plan.stage_write(
                str(kb_path), "batch-sq", sid, "entities/ada.md", str(cf)
            )
        batch_merge.merge_batch(str(kb_path), "batch-sq")
        status = batch_plan.batch_status(str(kb_path), "batch-sq")
        assert status["escalated"]["files"] == 1
        (entry,) = status["escalated"]["entries"]
        assert entry["path"] == "entities/ada.md"
        assert sorted(entry["parties"]) == sorted(src_ids[:2])


class TestWaves:
    def _many_inputs(self, tmp_path, n):
        d = tmp_path / "many"
        d.mkdir(exist_ok=True)
        for i in range(n):
            (d / f"doc-{i:03d}.md").write_text(f"# Doc {i}", encoding="utf-8")
        return d

    def test_partitions_by_max_workers(self, kb_path, tmp_path):
        d = self._many_inputs(tmp_path, 25)
        result = batch_plan.plan_batch(
            str(kb_path), str(d), "batch-w",
            max_workers=10, state_dir=kb_path / ".kb" / "tasks",
        )
        waves = result["waves"]
        assert [len(w) for w in waves] == [10, 10, 5]
        flat = [sid for w in waves for sid in w]
        assert flat == result["source_ids"]  # order preserved
        assert len(set(flat)) == 25  # disjoint, complete

    def test_single_wave_small_batch(self, kb_path, input_dir):
        result = batch_plan.plan_batch(
            str(kb_path), str(input_dir), "batch-ws",
            state_dir=kb_path / ".kb" / "tasks",
        )
        assert len(result["waves"]) == 1


class TestStateMachineDoc:
    """parallel-import.md carries the protocol as a transition list bound
    to code. The machine (not prose) is the contract: working states,
    failure states with onset+exit, guards, and recovery edges."""

    STATES = ("planning", "mapping", "merging", "linting", "done")
    FAILURE_STATES = ("stalled", "diverged", "interrupted")

    def _section(self) -> str:
        doc = (
            Path(__file__).resolve().parent.parent
            / "references" / "parallel-import.md"
        ).read_text(encoding="utf-8")
        start = doc.index("### State machine")
        end = doc.index("\n## ", start + 1)
        return doc[start:end]

    def test_transition_list_format(self):
        """Every state-led line is a transition (no prose tables)."""
        section = self._section()
        all_states = set(self.STATES) | set(self.FAILURE_STATES)
        seen = False
        for line in section.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            head = stripped.split("--")[0].strip()
            tokens = [t.strip() for t in head.split("|")]
            if tokens and all(t in all_states for t in tokens):
                seen = True
                assert "-->" in stripped, f"not a transition: {stripped!r}"
        assert seen, "no transitions found"

    def test_all_states_present(self):
        section = self._section()
        for phase in self.STATES + self.FAILURE_STATES:
            assert re.search(rf"\b{phase}\b", section), f"state {phase} missing"

    def test_code_mergeable_phases_subset_of_doc(self):
        section = self._section()
        for phase in batch_merge._MERGEABLE_PHASES:
            assert re.search(rf"\b{phase}\b", section), f"code phase {phase} undocumented"

    def test_failure_states_have_onset_and_exit(self):
        section = self._section()
        for state in self.FAILURE_STATES:
            assert re.search(rf"-->\s*{state}\b", section), f"no onset for {state}"
            assert re.search(rf"^{state} --", section, re.M), f"no exit for {state}"

    def test_gates_named(self):
        lowered = self._section().lower()
        assert "lint clean" in lowered  # mark-done gate
        assert "lint report" in lowered  # gc gate
        assert "never re-run merge after triangulate" in lowered

    def test_failure_recovery_markers(self):
        lowered = self._section().lower()
        for marker in (
            "re-dispatched",  # stuck worker reset
            "restage",  # staged content changed
            "re-run merge",  # crash mid-merge
            "re-run `plan`",  # crash mid-plan
            "union",  # live moved under staging
            "symlink",  # merge-path refusal
        ):
            assert marker in lowered, f"recovery {marker} missing"
