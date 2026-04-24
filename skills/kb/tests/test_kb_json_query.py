"""Tests for kb json_query.py — reopen narrow slices from JSON artifacts."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    script_dir = Path(__file__).resolve().parent.parent / "scripts"
    script_path = script_dir / "json_query.py"
    spec = importlib.util.spec_from_file_location("kb_json_query", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, str(script_dir))
    spec.loader.exec_module(module)
    return module


json_query = _load_module()


class TestQueryJsonArtifact:
    def test_selects_nested_list_and_filters_fields(self, tmp_path: Path):
        payload = {
            "pending_tasks": [
                {"task_id": "t1", "phase": "extracting"},
                {"task_id": "t2", "phase": "done"},
            ],
            "file_counts": {"entities": 3},
        }
        json_path = tmp_path / "open.json"
        json_path.write_text(json.dumps(payload), encoding="utf-8")

        result = json_query.query_json_artifact(
            json_path,
            selector="pending_tasks",
            where="phase=extracting",
            fields=["task_id"],
            limit=1,
        )

        assert result == [{"task_id": "t1"}]

    def test_selects_indexed_path(self, tmp_path: Path):
        payload = {"results": [{"file": "a.md"}, {"file": "b.md"}]}
        json_path = tmp_path / "search.json"
        json_path.write_text(json.dumps(payload), encoding="utf-8")

        result = json_query.query_json_artifact(json_path, selector="results[1]")

        assert result == {"file": "b.md"}


class TestJsonQueryCli:
    def test_main_writes_output_file_and_returns_envelope(self, tmp_path: Path, capsys):
        payload = {
            "pending_tasks": [
                {"task_id": "t1", "phase": "extracting"},
                {"task_id": "t2", "phase": "done"},
            ]
        }
        json_path = tmp_path / "tasks.json"
        json_path.write_text(json.dumps(payload), encoding="utf-8")
        output_path = tmp_path / "slice.json"

        json_query.main([
            "--file",
            str(json_path),
            "--selector",
            "pending_tasks",
            "--where",
            "phase=extracting",
            "--fields",
            "task_id",
            "--output",
            str(output_path),
        ])

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "kb-json-query"
        assert envelope["top_level_type"] == "array"
        assert envelope["item_count"] == 1
        assert json.loads(output_path.read_text(encoding="utf-8")) == [{"task_id": "t1"}]