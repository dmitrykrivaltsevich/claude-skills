"""Tests for state.py — multi-session task queue for KB operations."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import state
from contracts import ContractViolationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------
# init_task
# ---------------------------------------------------------------------------

class TestInitTask:
    def test_creates_task_file(self, state_dir: Path):
        result = state.init_task(
            task_id="add-paper-123",
            task_type="add",
            description="Ingest paper on quantum computing",
            kb_path="/tmp/my-kb",
            state_dir=state_dir,
        )
        path = state_dir / "add-paper-123.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["task_id"] == "add-paper-123"
        assert data["task_type"] == "add"
        assert data["description"] == "Ingest paper on quantum computing"
        assert data["kb_path"] == "/tmp/my-kb"
        assert data["phase"] == "registered"
        assert data["items"] == []
        assert "created_at" in data

    def test_returns_state_file_path(self, state_dir: Path):
        result = state.init_task(
            task_id="t1",
            task_type="add",
            description="Test",
            kb_path="/tmp/kb",
            state_dir=state_dir,
        )
        assert result["state_file"] == str(state_dir / "t1.json")
        assert result["resumed"] is False

    def test_resume_existing_task(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        state.add_items("t1", [{"title": "Chapter 1"}], state_dir=state_dir)
        result = state.init_task("t1", "add", "Other", "/tmp/kb2", state_dir=state_dir)
        assert result["resumed"] is True
        # Original data preserved
        data = json.loads((state_dir / "t1.json").read_text())
        assert data["description"] == "Test"
        assert len(data["items"]) == 1

    def test_rejects_empty_task_id(self, state_dir: Path):
        with pytest.raises(ContractViolationError, match="task_id"):
            state.init_task("", "add", "Test", "/tmp/kb", state_dir=state_dir)

    def test_rejects_empty_description(self, state_dir: Path):
        with pytest.raises(ContractViolationError, match="description"):
            state.init_task("t1", "add", "", "/tmp/kb", state_dir=state_dir)

    def test_rejects_invalid_task_type(self, state_dir: Path):
        with pytest.raises(ContractViolationError, match="task_type"):
            state.init_task("t1", "invalid", "Test", "/tmp/kb", state_dir=state_dir)


# ---------------------------------------------------------------------------
# add_items
# ---------------------------------------------------------------------------

class TestAddItems:
    def test_adds_items_with_auto_id(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        result = state.add_items(
            "t1",
            [{"title": "Chapter 1"}, {"title": "Chapter 2"}],
            state_dir=state_dir,
        )
        assert result["total_items"] == 2
        data = json.loads((state_dir / "t1.json").read_text())
        assert data["items"][0]["id"] == "i1"
        assert data["items"][0]["title"] == "Chapter 1"
        assert data["items"][0]["status"] == "pending"
        assert data["items"][1]["id"] == "i2"

    def test_appends_to_existing(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        state.add_items("t1", [{"title": "Ch1"}], state_dir=state_dir)
        result = state.add_items("t1", [{"title": "Ch2"}], state_dir=state_dir)
        assert result["total_items"] == 2

    def test_rejects_empty_items(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        with pytest.raises(ContractViolationError, match="At least one item"):
            state.add_items("t1", [], state_dir=state_dir)

    def test_deduplicates_by_title(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        state.add_items("t1", [{"title": "Ch1"}], state_dir=state_dir)
        result = state.add_items("t1", [{"title": "Ch1"}, {"title": "Ch2"}], state_dir=state_dir)
        assert result["total_items"] == 2  # Ch1 deduped


# ---------------------------------------------------------------------------
# update_item
# ---------------------------------------------------------------------------

class TestUpdateItem:
    def test_updates_status(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        state.add_items("t1", [{"title": "Ch1"}], state_dir=state_dir)
        result = state.update_item("t1", "i1", "done", state_dir=state_dir)
        assert result["item_id"] == "i1"
        assert result["status"] == "done"

    def test_rejects_invalid_status(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        state.add_items("t1", [{"title": "Ch1"}], state_dir=state_dir)
        with pytest.raises(ContractViolationError, match="status"):
            state.update_item("t1", "i1", "invalid", state_dir=state_dir)

    def test_raises_on_missing_item(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        with pytest.raises(ContractViolationError, match="not found"):
            state.update_item("t1", "i999", "done", state_dir=state_dir)

    def test_stores_notes_on_item(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        state.add_items("t1", [{"title": "Ch1"}], state_dir=state_dir)
        result = state.update_item(
            "t1", "i1", "done",
            notes="+3E +2T +1I (dijkstra, parnas, brooks)",
            state_dir=state_dir,
        )
        assert result["notes"] == "+3E +2T +1I (dijkstra, parnas, brooks)"
        data = json.loads((state_dir / "t1.json").read_text())
        assert data["items"][0]["notes"] == "+3E +2T +1I (dijkstra, parnas, brooks)"

    def test_notes_omitted_when_not_provided(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        state.add_items("t1", [{"title": "Ch1"}], state_dir=state_dir)
        result = state.update_item("t1", "i1", "done", state_dir=state_dir)
        assert "notes" not in result
        data = json.loads((state_dir / "t1.json").read_text())
        assert "notes" not in data["items"][0]

    def test_notes_can_be_updated(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        state.add_items("t1", [{"title": "Ch1"}], state_dir=state_dir)
        state.update_item("t1", "i1", "done", notes="v1", state_dir=state_dir)
        state.update_item("t1", "i1", "done", notes="v2", state_dir=state_dir)
        data = json.loads((state_dir / "t1.json").read_text())
        assert data["items"][0]["notes"] == "v2"


# ---------------------------------------------------------------------------
# update_phase
# ---------------------------------------------------------------------------

class TestUpdatePhase:
    def test_updates_phase(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        result = state.update_phase("t1", "extracting", state_dir=state_dir)
        assert result["phase"] == "extracting"

    def test_rejects_invalid_phase(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        with pytest.raises(ContractViolationError, match="phase"):
            state.update_phase("t1", "invalid", state_dir=state_dir)


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_returns_summary(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        state.add_items(
            "t1",
            [{"title": "Ch1"}, {"title": "Ch2"}, {"title": "Ch3"}],
            state_dir=state_dir,
        )
        state.update_item("t1", "i1", "done", state_dir=state_dir)
        result = state.get_status("t1", state_dir=state_dir)
        assert result["task_id"] == "t1"
        assert result["total_items"] == 3
        assert result["done"] == 1
        assert result["pending"] == 2
        assert result["in_progress"] == 0


# ---------------------------------------------------------------------------
# pending
# ---------------------------------------------------------------------------

class TestPending:
    def test_returns_pending_items(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        state.add_items(
            "t1",
            [{"title": "Ch1"}, {"title": "Ch2"}, {"title": "Ch3"}],
            state_dir=state_dir,
        )
        state.update_item("t1", "i1", "done", state_dir=state_dir)
        result = state.pending("t1", state_dir=state_dir)
        assert len(result["next_items"]) == 2
        assert result["next_items"][0]["id"] == "i2"

    def test_limit(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        state.add_items(
            "t1",
            [{"title": f"Ch{i}"} for i in range(10)],
            state_dir=state_dir,
        )
        result = state.pending("t1", limit=3, state_dir=state_dir)
        assert len(result["next_items"]) == 3

    def test_recent_completed_includes_notes(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        state.add_items(
            "t1",
            [{"title": "Ch1"}, {"title": "Ch2"}, {"title": "Ch3"}],
            state_dir=state_dir,
        )
        state.update_item(
            "t1", "i1", "done", notes="+3E +2T", state_dir=state_dir,
        )
        result = state.pending("t1", state_dir=state_dir)
        assert len(result["recent_completed"]) == 1
        assert result["recent_completed"][0]["notes"] == "+3E +2T"
        assert result["recent_completed"][0]["title"] == "Ch1"

    def test_recent_completed_skips_items_without_notes(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        state.add_items(
            "t1",
            [{"title": "Ch1"}, {"title": "Ch2"}],
            state_dir=state_dir,
        )
        state.update_item("t1", "i1", "done", state_dir=state_dir)  # no notes
        result = state.pending("t1", state_dir=state_dir)
        assert result["recent_completed"] == []

    def test_recent_completed_limited_to_5(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        state.add_items(
            "t1",
            [{"title": f"Ch{i}"} for i in range(8)],
            state_dir=state_dir,
        )
        for i in range(1, 8):
            state.update_item(
                "t1", f"i{i}", "done", notes=f"notes-{i}",
                state_dir=state_dir,
            )
        result = state.pending("t1", state_dir=state_dir)
        assert len(result["recent_completed"]) == 5
        # Should be the last 5 (i3..i7)
        assert result["recent_completed"][0]["notes"] == "notes-3"


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------

class TestListTasks:
    def test_lists_all_tasks(self, state_dir: Path):
        state.init_task("t1", "add", "First", "/tmp/kb", state_dir=state_dir)
        state.init_task("t2", "lint", "Second", "/tmp/kb", state_dir=state_dir)
        result = state.list_tasks(state_dir=state_dir)
        assert len(result["tasks"]) == 2
        ids = {t["task_id"] for t in result["tasks"]}
        assert ids == {"t1", "t2"}

    def test_empty_dir(self, state_dir: Path):
        result = state.list_tasks(state_dir=state_dir)
        assert result["tasks"] == []


# ---------------------------------------------------------------------------
# export_task
# ---------------------------------------------------------------------------

class TestExportTask:
    def test_exports_full_state(self, state_dir: Path):
        state.init_task("t1", "add", "Test", "/tmp/kb", state_dir=state_dir)
        state.add_items("t1", [{"title": "Ch1"}], state_dir=state_dir)
        result = state.export_task("t1", state_dir=state_dir)
        assert result["task_id"] == "t1"
        assert len(result["items"]) == 1


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------

class TestCli:
    def test_init_cli(self, state_dir: Path, capsys):
        state.main([
            "init",
            "--task-id", "t1",
            "--task-type", "add",
            "--description", "Test",
            "--kb-path", "/tmp/kb",
            "--state-dir", str(state_dir),
        ])
        out = json.loads(capsys.readouterr().out)
        assert out["task_id"] == "t1"

    def test_status_cli(self, state_dir: Path, capsys):
        state.main([
            "init",
            "--task-id", "t1",
            "--task-type", "add",
            "--description", "Test",
            "--kb-path", "/tmp/kb",
            "--state-dir", str(state_dir),
        ])
        capsys.readouterr()  # discard init output
        state.main([
            "status",
            "--task-id", "t1",
            "--state-dir", str(state_dir),
        ])
        out = json.loads(capsys.readouterr().out)
        assert out["task_id"] == "t1"
