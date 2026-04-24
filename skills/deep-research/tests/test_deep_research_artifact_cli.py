"""CLI tests for deep-research artifact mode."""

from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import discover
import state


class TestDiscoverArtifactMode:
    def test_main_writes_output_file_and_returns_envelope(
        self, tmp_path: Path, capsys
    ):
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "demo-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            textwrap.dedent(
                """\
                ---
                name: demo-skill
                description: Demo skill.
                ---

                # Demo
                """
            ),
            encoding="utf-8",
        )
        output_path = tmp_path / "discover.json"

        discover.main(["--skills-dir", str(skills_dir), "--output", str(output_path)])

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "deep-research-skill-discovery"
        assert envelope["top_level_type"] == "array"
        assert envelope["item_count"] == 1
        assert json.loads(output_path.read_text(encoding="utf-8"))[0]["name"] == "demo-skill"


class TestStateArtifactMode:
    def test_export_writes_output_file_and_returns_envelope(
        self, tmp_path: Path, capsys
    ):
        state_dir = tmp_path / "state"
        state.init_research("demo", "Goal", state_dir=state_dir)
        state.add_questions("demo", ["Q1"], state_dir=state_dir)
        output_path = tmp_path / "export.json"

        state.main([
            "export",
            "--research-id",
            "demo",
            "--state-dir",
            str(state_dir),
            "--output",
            str(output_path),
        ])

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "deep-research-state-export"
        assert envelope["top_level_type"] == "object"
        exported = json.loads(output_path.read_text(encoding="utf-8"))
        assert exported["research_id"] == "demo"
        assert exported["questions"][0]["text"] == "Q1"