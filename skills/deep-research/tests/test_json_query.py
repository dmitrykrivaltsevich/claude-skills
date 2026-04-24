"""Tests for json_query.py — reopen narrow slices from JSON artifacts."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import json_query


class TestQueryJsonArtifact:
    def test_selects_nested_list_and_filters_fields(self, tmp_path: Path):
        payload = {
            "questions": [
                {"text": "Q1", "status": "covered"},
                {"text": "Q2", "status": "partially"},
            ],
            "facts": [{"id": "f1", "claim": "Fact"}],
        }
        json_path = tmp_path / "state.json"
        json_path.write_text(json.dumps(payload), encoding="utf-8")

        result = json_query.query_json_artifact(
            json_path,
            selector="questions",
            where="status=covered",
            fields=["text"],
            limit=1,
        )

        assert result == [{"text": "Q1"}]

    def test_selects_indexed_path(self, tmp_path: Path):
        payload = {"facts": [{"id": "f1", "claim": "Fact 1"}, {"id": "f2", "claim": "Fact 2"}]}
        json_path = tmp_path / "state.json"
        json_path.write_text(json.dumps(payload), encoding="utf-8")

        result = json_query.query_json_artifact(json_path, selector="facts[1]")

        assert result == {"id": "f2", "claim": "Fact 2"}


class TestJsonQueryCli:
    def test_main_writes_output_file_and_returns_envelope(self, tmp_path: Path, capsys):
        payload = {
            "questions": [
                {"text": "Q1", "status": "covered"},
                {"text": "Q2", "status": "unexplored"},
            ]
        }
        json_path = tmp_path / "state.json"
        json_path.write_text(json.dumps(payload), encoding="utf-8")
        output_path = tmp_path / "query-result.json"

        json_query.main([
            "--file",
            str(json_path),
            "--selector",
            "questions",
            "--where",
            "status=covered",
            "--fields",
            "text",
            "--output",
            str(output_path),
        ])

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "deep-research-json-query"
        assert envelope["top_level_type"] == "array"
        assert envelope["item_count"] == 1
        assert json.loads(output_path.read_text(encoding="utf-8")) == [{"text": "Q1"}]