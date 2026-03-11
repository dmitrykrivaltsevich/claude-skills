"""Tests for discover.py — skill scanner that builds a capability map."""

from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import discover


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_SKILL_MD = textwrap.dedent("""\
    ---
    name: test-skill
    description: A test skill for unit tests. Use when testing.
    allowed-tools:
      - Bash(uv run *)
    ---

    # Test Skill

    ## Script Decision Guide

    | User says… | Script | What it returns |
    |---|---|---|
    | "search for X" | `search.py text` | JSON array of results |
    | "download this" | `download.py` | Saved file |
""")

SKILL_MD_NO_TABLE = textwrap.dedent("""\
    ---
    name: bare-skill
    description: No table here.
    ---

    # Bare Skill

    Just some text, no scripts.
""")

SKILL_MD_NO_FRONTMATTER = textwrap.dedent("""\
    # No Frontmatter

    Just markdown.
""")

SKILL_MD_MULTI_TABLE = textwrap.dedent("""\
    ---
    name: multi-table
    description: Has multiple tables. Use when multi-testing.
    ---

    # Multi

    ## Script Decision Guide

    | User says… | Script | What it returns |
    |---|---|---|
    | "do X" | `alpha.py` | JSON |
    | "do Y" | `beta.py --flag` | Text |

    ## Another Table

    | Column A | Column B |
    |---|---|
    | foo | bar |
""")


@pytest.fixture
def skill_tree(tmp_path: Path) -> Path:
    """Create a minimal skill directory tree for testing."""
    skills_dir = tmp_path / "skills"

    # Skill 1: has a decision table
    s1 = skills_dir / "test-skill"
    s1.mkdir(parents=True)
    (s1 / "SKILL.md").write_text(MINIMAL_SKILL_MD, encoding="utf-8")

    # Skill 2: no table
    s2 = skills_dir / "bare-skill"
    s2.mkdir(parents=True)
    (s2 / "SKILL.md").write_text(SKILL_MD_NO_TABLE, encoding="utf-8")

    # Skill 3: no frontmatter at all
    s3 = skills_dir / "no-front"
    s3.mkdir(parents=True)
    (s3 / "SKILL.md").write_text(SKILL_MD_NO_FRONTMATTER, encoding="utf-8")

    # Skill 4: multi-table
    s4 = skills_dir / "multi-table"
    s4.mkdir(parents=True)
    (s4 / "SKILL.md").write_text(SKILL_MD_MULTI_TABLE, encoding="utf-8")

    # Not a skill — random dir inside skills/
    (skills_dir / "not-a-skill").mkdir(parents=True)
    (skills_dir / "not-a-skill" / "random.txt").write_text("hi")

    # Skill 5: nested inside a plugin wrapper dir (like google-drive/drive)
    wrapper = skills_dir / "plugin-wrapper"
    s5 = wrapper / "nested-skill"
    s5.mkdir(parents=True)
    (s5 / "SKILL.md").write_text(SKILL_MD_NO_TABLE, encoding="utf-8")

    return skills_dir


# ---------------------------------------------------------------------------
# parse_frontmatter tests
# ---------------------------------------------------------------------------

class TestParseFrontmatter:
    def test_extracts_name_and_description(self):
        fm = discover.parse_frontmatter(MINIMAL_SKILL_MD)
        assert fm["name"] == "test-skill"
        assert "test skill" in fm["description"].lower()

    def test_no_frontmatter_returns_empty(self):
        fm = discover.parse_frontmatter(SKILL_MD_NO_FRONTMATTER)
        assert fm == {}

    def test_preserves_allowed_tools(self):
        fm = discover.parse_frontmatter(MINIMAL_SKILL_MD)
        assert "allowed-tools" in fm
        assert isinstance(fm["allowed-tools"], list)

    def test_empty_string_returns_empty(self):
        fm = discover.parse_frontmatter("")
        assert fm == {}


# ---------------------------------------------------------------------------
# extract_script_commands tests
# ---------------------------------------------------------------------------

class TestExtractScriptCommands:
    def test_extracts_commands_from_table(self):
        cmds = discover.extract_script_commands(MINIMAL_SKILL_MD)
        assert len(cmds) == 2
        triggers = [c["trigger"] for c in cmds]
        assert "search for X" in triggers
        scripts = [c["script"] for c in cmds]
        assert "search.py text" in scripts

    def test_no_table_returns_empty(self):
        cmds = discover.extract_script_commands(SKILL_MD_NO_TABLE)
        assert cmds == []

    def test_multi_table_extracts_only_script_table(self):
        cmds = discover.extract_script_commands(SKILL_MD_MULTI_TABLE)
        # Should pick up alpha.py and beta.py, NOT the foo/bar table
        scripts = [c["script"] for c in cmds]
        assert "alpha.py" in scripts
        assert "beta.py --flag" in scripts
        assert len(cmds) == 2

    def test_captures_return_description(self):
        cmds = discover.extract_script_commands(MINIMAL_SKILL_MD)
        returns = [c["returns"] for c in cmds]
        assert any("JSON" in r for r in returns)


# ---------------------------------------------------------------------------
# scan_skill tests
# ---------------------------------------------------------------------------

class TestScanSkill:
    def test_scan_valid_skill(self, skill_tree: Path):
        result = discover.scan_skill(skill_tree / "test-skill")
        assert result["name"] == "test-skill"
        assert len(result["commands"]) == 2
        assert "description" in result

    def test_scan_no_skill_md_returns_none(self, skill_tree: Path):
        result = discover.scan_skill(skill_tree / "not-a-skill")
        assert result is None

    def test_scan_no_frontmatter_still_works(self, skill_tree: Path):
        result = discover.scan_skill(skill_tree / "no-front")
        assert result is not None
        assert result["name"] == "no-front"  # falls back to dir name
        assert result["commands"] == []


# ---------------------------------------------------------------------------
# discover_skills tests
# ---------------------------------------------------------------------------

class TestDiscoverSkills:
    def test_discovers_all_valid_skills(self, skill_tree: Path):
        skills = discover.discover_skills(skill_tree)
        names = {s["name"] for s in skills}
        assert "test-skill" in names
        assert "bare-skill" in names
        assert "multi-table" in names
        # no-front has no frontmatter name → falls back to dir name
        assert "no-front" in names

    def test_discovers_nested_skills(self, skill_tree: Path):
        """Skills nested inside wrapper dirs (e.g. google-drive/drive/) are found."""
        skills = discover.discover_skills(skill_tree)
        paths = {s["path"] for s in skills}
        nested_path = str(skill_tree / "plugin-wrapper" / "nested-skill")
        assert nested_path in paths

    def test_skips_non_skill_dirs(self, skill_tree: Path):
        skills = discover.discover_skills(skill_tree)
        names = {s["name"] for s in skills}
        assert "not-a-skill" not in names

    def test_returns_sorted_by_name(self, skill_tree: Path):
        skills = discover.discover_skills(skill_tree)
        names = [s["name"] for s in skills]
        assert names == sorted(names)

    def test_nonexistent_dir_returns_empty(self, tmp_path: Path):
        skills = discover.discover_skills(tmp_path / "nope")
        assert skills == []

    def test_output_is_json_serializable(self, skill_tree: Path):
        skills = discover.discover_skills(skill_tree)
        # Should not raise
        json.dumps(skills, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLI:
    def test_cli_outputs_json(self, skill_tree: Path, capsys):
        discover.main(["--skills-dir", str(skill_tree)])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) >= 4

    def test_cli_with_nonexistent_dir(self, tmp_path: Path, capsys):
        discover.main(["--skills-dir", str(tmp_path / "nope")])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == []
