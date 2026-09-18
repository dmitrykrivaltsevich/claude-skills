"""Tests for schema-aligned batch staging — custom knowledge/ top dirs.

A KB may declare custom entry types in .kb/rules.md with their own
directories (e.g. knowledge/experiments/, knowledge/rollouts/ — see
references/entry-types.md "Custom Entry Types"). The batch staging gate
must accept those alongside the built-ins:

- live-FS source of truth: any valid-named dir already under knowledge/
- manifest-declared intent: plan(allow_dirs=[...]) for empty KBs where
  the dir does not exist yet (workers are staging-only and cannot mkdir
  live dirs themselves).

Unit of work: one custom-dir entry through stage→merge. Checkpoint
artifact: manifest allowed_tops. Resume path: re-run plan (same inputs).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from ._loader import load_script_module

batch_plan = load_script_module("kb_test_schema_plan", "batch_plan.py")
batch_merge = load_script_module("kb_test_schema_merge", "batch_merge.py")
init = load_script_module("kb_test_schema_init", "init.py")
search = load_script_module("kb_test_schema_search", "search.py")


def expect_violation(fn, pattern: str) -> None:
    """Match on type name + message (loader sandboxes each script module,
    so ContractViolationError identities differ per module)."""
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
    (d / "alpha.md").write_text("# Alpha\n\nContent about Grace.", encoding="utf-8")
    return d


def _plan(kb_path: Path, input_dir: Path, **kwargs) -> dict:
    return batch_plan.plan_batch(
        str(kb_path),
        str(input_dir),
        "batch-001",
        state_dir=kb_path / ".kb" / "tasks",
        **kwargs,
    )


def _manifest(kb_path: Path) -> dict:
    return json.loads(
        (kb_path / ".kb" / "batches" / "batch-001" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )


EXPERIMENT_BODY = (
    "---\ntype: experiment\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
    "source-ids: [{sid}]\ntags: [optics]\n---\n\n# Prism Trial\n\nResult one.\n"
)


class TestPlanAllowDirs:
    def test_plan_stores_allowed_tops(self, kb_path: Path, input_dir: Path):
        result = _plan(kb_path, input_dir, allow_dirs=["rollouts", "experiments"])
        assert result["allowed_tops"] == ["experiments", "rollouts"]
        assert _manifest(kb_path)["allowed_tops"] == ["experiments", "rollouts"]

    def test_plan_defaults_to_empty_allowed_tops(
        self, kb_path: Path, input_dir: Path
    ):
        result = _plan(kb_path, input_dir)
        assert result["allowed_tops"] == []
        assert _manifest(kb_path)["allowed_tops"] == []

    def test_plan_rejects_malformed_allow_dir(
        self, kb_path: Path, input_dir: Path
    ):
        expect_violation(
            lambda: _plan(kb_path, input_dir, allow_dirs=["Bad Name!"]),
            r"allow_dirs",
        )
        expect_violation(
            lambda: _plan(kb_path, input_dir, allow_dirs=[".hidden"]),
            r"allow_dirs",
        )

    def test_resumed_plan_returns_allowed_tops(
        self, kb_path: Path, input_dir: Path
    ):
        _plan(kb_path, input_dir, allow_dirs=["experiments"])
        second = _plan(kb_path, input_dir)
        assert second["resumed"] is True
        assert second["allowed_tops"] == ["experiments"]


class TestStageWriteCustomDirs:
    def _stage(
        self, kb_path: Path, sid: str, rel: str, body: str | None = None
    ) -> dict:
        cf = kb_path / f"content-{sid}.md"
        cf.write_text(
            (body or EXPERIMENT_BODY).format(sid=sid), encoding="utf-8"
        )
        return batch_plan.stage_write(str(kb_path), "batch-001", sid, rel, str(cf))

    def test_empty_kb_custom_dir_with_allow_dirs(
        self, kb_path: Path, input_dir: Path
    ):
        # Fresh scaffold has no knowledge/experiments/ — the manifest
        # declaration is what admits the path.
        assert not (kb_path / "knowledge" / "experiments").exists()
        planned = _plan(kb_path, input_dir, allow_dirs=["experiments"])
        record = self._stage(kb_path, planned["source_ids"][0], "experiments/prism.md")
        assert record["op"] == "create"
        assert record["path"] == "experiments/prism.md"

    def test_existing_live_dir_needs_no_flag(
        self, kb_path: Path, input_dir: Path
    ):
        (kb_path / "knowledge" / "rollouts").mkdir()
        planned = _plan(kb_path, input_dir)
        record = self._stage(kb_path, planned["source_ids"][0], "rollouts/v2.md")
        assert record["op"] == "create"

    def test_undeclared_custom_dir_rejected(
        self, kb_path: Path, input_dir: Path
    ):
        planned = _plan(kb_path, input_dir)
        expect_violation(
            lambda: self._stage(
                kb_path, planned["source_ids"][0], "experiments/prism.md"
            ),
            r"allow-dirs",
        )

    def test_typo_top_still_rejected(self, kb_path: Path, input_dir: Path):
        planned = _plan(kb_path, input_dir)
        expect_violation(
            lambda: self._stage(
                kb_path, planned["source_ids"][0], "entites/ada.md"
            ),
            r"entites",
        )

    def test_allow_dirs_do_not_weaken_other_gates(
        self, kb_path: Path, input_dir: Path
    ):
        planned = _plan(kb_path, input_dir, allow_dirs=["experiments"])
        sid = planned["source_ids"][0]
        # Coordinator-owned paths stay forbidden even with declarations.
        expect_violation(
            lambda: self._stage(kb_path, sid, "index.md"), r"forbidden"
        )
        # Declaring assets changes nothing about per-source namespacing.
        blob = kb_path / "blob.bin"
        blob.write_bytes(b"\x00\x01")
        cf = kb_path / "blob-src.md"
        cf.write_text("x", encoding="utf-8")
        expect_violation(
            lambda: batch_plan.stage_write(
                str(kb_path), "batch-001", sid, "assets/other-src/logo.png", str(blob)
            ),
            r"namespaced",
        )

    def test_old_manifest_without_key_still_stages_builtin(
        self, kb_path: Path, input_dir: Path
    ):
        planned = _plan(kb_path, input_dir)
        manifest_path = kb_path / ".kb" / "batches" / "batch-001" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        del manifest["allowed_tops"]  # pre-feature batch layout
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        record = self._stage(
            kb_path,
            planned["source_ids"][0],
            "entities/ada.md",
            "---\ntype: entity\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            "source-ids: [{sid}]\ntags: []\n---\n\n# Ada\n\nFact.\n",
        )
        assert record["op"] == "create"


class TestMergeCustomDirs:
    def test_merge_applies_custom_dir_and_index_heading(
        self, kb_path: Path, input_dir: Path
    ):
        planned = _plan(kb_path, input_dir, allow_dirs=["experiments"])
        sid = planned["source_ids"][0]
        cf = kb_path / "exp.md"
        cf.write_text(EXPERIMENT_BODY.format(sid=sid), encoding="utf-8")
        batch_plan.stage_write(
            str(kb_path), "batch-001", sid, "experiments/prism.md", str(cf)
        )
        result = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert result["applied"] == 1
        live = kb_path / "knowledge" / "experiments" / "prism.md"
        assert live.exists()
        assert "Result one." in live.read_text(encoding="utf-8")
        index = (kb_path / "index.md").read_text(encoding="utf-8")
        assert "## Experiments" in index
        assert "[[prism]]" in index

    def test_merge_replay_over_custom_dir_is_noop(
        self, kb_path: Path, input_dir: Path
    ):
        planned = _plan(kb_path, input_dir, allow_dirs=["experiments"])
        sid = planned["source_ids"][0]
        cf = kb_path / "exp.md"
        cf.write_text(EXPERIMENT_BODY.format(sid=sid), encoding="utf-8")
        batch_plan.stage_write(
            str(kb_path), "batch-001", sid, "experiments/prism.md", str(cf)
        )
        first = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert first["applied"] == 1
        before = (kb_path / "knowledge" / "experiments" / "prism.md").read_bytes()
        index_before = (kb_path / "index.md").read_text(encoding="utf-8")
        second = batch_merge.merge_batch(str(kb_path), "batch-001")
        assert second["applied"] == 0
        assert (kb_path / "knowledge" / "experiments" / "prism.md").read_bytes() == before
        assert (kb_path / "index.md").read_text(encoding="utf-8") == index_before

    def test_merge_rejects_hand_written_undeclared_custom_path(
        self, kb_path: Path, input_dir: Path
    ):
        # Defense in depth: ops.jsonl may be hand-written, so merge
        # re-validates against the same union (builtin + live + manifest).
        planned = _plan(kb_path, input_dir)
        sid = planned["source_ids"][0]
        staging = kb_path / ".kb" / "batches" / "batch-001" / "staging" / sid
        staging.mkdir(parents=True)
        (staging / "evil.md").write_text("planted", encoding="utf-8")
        (staging / "ops.jsonl").write_text(
            json.dumps(
                {
                    "op": "create",
                    "path": "shadow/evil.md",
                    "base_sha1": "",
                    "staged_sha1": "0" * 40,
                    "source_id": sid,
                    "staged_at": "2026-01-01T00:00:00+00:00",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        expect_violation(
            lambda: batch_merge.merge_batch(str(kb_path), "batch-001"),
            r"shadow",
        )


class TestSearchCustomCategory:
    def test_search_custom_category(self, kb_path: Path):
        custom = kb_path / "knowledge" / "experiments"
        custom.mkdir()
        (custom / "prism.md").write_text(
            "# Prism Trial\n\nRefraction zxylophone result.\n", encoding="utf-8"
        )
        result = search.search_kb(str(kb_path), "zxylophone", category="experiments")
        assert [r["file"] for r in result["results"]] == [
            "knowledge/experiments/prism.md"
        ]

    def test_search_missing_category_returns_empty(self, kb_path: Path):
        result = search.search_kb(str(kb_path), "anything", category="rollouts")
        assert result["results"] == []
        assert result["total_scanned"] == 0

    def test_search_malformed_category_rejected(self, kb_path: Path):
        expect_violation(
            lambda: search.search_kb(str(kb_path), "x", category="../evil"),
            r"category",
        )
        expect_violation(
            lambda: search.search_kb(str(kb_path), "x", category="Bad Name!"),
            r"category",
        )

    def test_search_cli_custom_category(self, kb_path: Path, capsys):
        custom = kb_path / "knowledge" / "experiments"
        custom.mkdir()
        (custom / "prism.md").write_text(
            "# Prism Trial\n\nRefraction zxylophone result.\n", encoding="utf-8"
        )
        search.main(
            ["--path", str(kb_path), "--query", "zxylophone",
             "--category", "experiments"]
        )
        out = json.loads(capsys.readouterr().out)
        assert [r["file"] for r in out["results"]] == [
            "knowledge/experiments/prism.md"
        ]

    def test_search_cli_bad_category_exits_cleanly(self, kb_path: Path, capsys):
        # No traceback: main() converts the contract error to an
        # "ERROR: ..." stderr line + exit 1, like the other scripts.
        with pytest.raises(SystemExit) as exc_info:
            search.main(
                ["--path", str(kb_path), "--query", "x",
                 "--category", "../evil"]
            )
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert captured.err.startswith("ERROR: category must be")
        assert "Traceback" not in captured.err
