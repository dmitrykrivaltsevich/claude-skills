# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pytest >= 8.0",
# ]
# ///
"""Tests for pdf json_query helper."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_json_query_module():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "json_query.py"
    spec = importlib.util.spec_from_file_location("pdf_json_query", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


json_query = _load_json_query_module()


class TestPdfJsonQuery:
    def test_selects_filters_fields_and_limit(self, tmp_path: Path):
        payload = {
            "pages": [
                {"number": 1, "topic": "intro", "word_count": 120},
                {"number": 2, "topic": "methods", "word_count": 800},
                {"number": 3, "topic": "methods", "word_count": 700},
            ],
            "total_pages": 3,
        }
        artifact = tmp_path / "read.json"
        artifact.write_text(json.dumps(payload), encoding="utf-8")

        result = json_query.query_json_artifact(
            artifact,
            selector="pages",
            where="topic=methods",
            fields=["number", "word_count"],
            limit=1,
        )

        assert result == [{"number": 2, "word_count": 800}]

    def test_cli_output_writes_artifact_and_returns_envelope(self, tmp_path: Path, capsys):
        payload = {
            "pages": [
                {"number": 1, "word_count": 120},
                {"number": 2, "word_count": 450},
            ]
        }
        artifact = tmp_path / "read.json"
        artifact.write_text(json.dumps(payload), encoding="utf-8")
        output_path = tmp_path / "subset.json"

        json_query.main([
            "--file",
            str(artifact),
            "--selector",
            "pages",
            "--where",
            "word_count=450",
            "--fields",
            "number",
            "word_count",
            "--output",
            str(output_path),
        ])

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "pdf-json-query"
        assert json.loads(output_path.read_text(encoding="utf-8")) == [{"number": 2, "word_count": 450}]
