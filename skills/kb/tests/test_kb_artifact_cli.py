"""CLI tests for kb artifact mode."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path


def _load_module(module_name: str, file_name: str):
    script_dir = Path(__file__).resolve().parent.parent / "scripts"
    script_path = script_dir / file_name
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, str(script_dir))
    spec.loader.exec_module(module)
    return module


init = _load_module("kb_init", "init.py")
open_kb = _load_module("kb_open", "open.py")
state = _load_module("kb_state", "state.py")
topology = _load_module("kb_topology", "topology.py")


class TestOpenArtifactMode:
    def test_main_writes_output_file_and_returns_envelope(self, tmp_path: Path, capsys):
        kb_path = tmp_path / "kb"
        init.scaffold_kb(str(kb_path), "Artifact KB")
        output_path = tmp_path / "open.json"

        open_kb.main(["--path", str(kb_path), "--output", str(output_path)])

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "kb-open-context"
        assert envelope["top_level_type"] == "object"
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["name"] == "Artifact KB"


class TestStateArtifactMode:
    def test_export_writes_output_file_and_returns_envelope(self, tmp_path: Path, capsys):
        state_dir = tmp_path / "tasks"
        state.init_task("t1", "add", "Ingest source", "/tmp/kb", state_dir=state_dir)
        output_path = tmp_path / "task.json"

        state.main([
            "export",
            "--task-id",
            "t1",
            "--state-dir",
            str(state_dir),
            "--output",
            str(output_path),
        ])

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "kb-task-export"
        assert envelope["top_level_type"] == "object"
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["task_id"] == "t1"


class TestTopologyArtifactMode:
    def test_main_writes_output_file_and_returns_envelope(self, tmp_path: Path, capsys):
        kb_path = tmp_path / "kb"
        init.scaffold_kb(str(kb_path), "Graph KB")
        entity_path = kb_path / "knowledge" / "entities" / "ada.md"
        entity_path.write_text("# Ada\n[[algorithms]]\n", encoding="utf-8")
        topic_path = kb_path / "knowledge" / "topics" / "algorithms.md"
        topic_path.write_text("# Algorithms\n[[ada]]\n", encoding="utf-8")
        output_path = tmp_path / "topology.json"

        original_argv = sys.argv[:]
        sys.argv = ["topology.py", "--path", str(kb_path), "--output", str(output_path)]
        try:
            topology.main()
        finally:
            sys.argv = original_argv

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "kb-topology-analysis"
        assert envelope["top_level_type"] == "object"
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["total_nodes"] == 2