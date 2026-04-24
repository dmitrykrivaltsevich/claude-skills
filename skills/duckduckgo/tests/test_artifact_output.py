"""Tests for artifact_output.py — file-backed JSON emission helpers."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from artifact_output import emit_json_result


class TestEmitJsonResult:
    """Test file-backed emission for large JSON payloads."""

    def test_writes_list_payload_and_emits_envelope(self, tmp_path: Path, capsys):
        output_path = tmp_path / "search-results.json"
        payload = [{"title": "One"}, {"title": "Two"}]

        emit_json_result(
            payload,
            output_path=output_path,
            artifact_kind="duckduckgo-search-results",
        )

        stdout = capsys.readouterr().out
        envelope = json.loads(stdout)

        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "duckduckgo-search-results"
        assert envelope["top_level_type"] == "array"
        assert envelope["item_count"] == 2
        assert output_path.exists()
        assert json.loads(output_path.read_text(encoding="utf-8")) == payload

    def test_writes_dict_payload_and_emits_envelope(self, tmp_path: Path, capsys):
        output_path = tmp_path / "fact-check.json"
        payload = {"claim": "x", "tiers": {"wires": []}}

        emit_json_result(
            payload,
            output_path=output_path,
            artifact_kind="duckduckgo-fact-check",
        )

        stdout = capsys.readouterr().out
        envelope = json.loads(stdout)

        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "duckduckgo-fact-check"
        assert envelope["top_level_type"] == "object"
        assert envelope["keys"] == ["claim", "tiers"]
        assert output_path.exists()
        assert json.loads(output_path.read_text(encoding="utf-8")) == payload