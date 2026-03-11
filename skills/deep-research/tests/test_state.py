"""Tests for state.py — research state CRUD with JSON persistence."""

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
    """Override default state dir to tmp_path."""
    return tmp_path


@pytest.fixture
def research_file(state_dir: Path) -> Path:
    return state_dir / "test-research.json"


# ---------------------------------------------------------------------------
# init_research tests
# ---------------------------------------------------------------------------

class TestInitResearch:
    def test_creates_new_state_file(self, research_file: Path):
        result = state.init_research(
            research_id="test-research",
            goal="Understand quantum computing trends",
            state_dir=research_file.parent,
        )
        assert research_file.exists()
        data = json.loads(research_file.read_text(encoding="utf-8"))
        assert data["research_id"] == "test-research"
        assert data["goal"] == "Understand quantum computing trends"
        assert data["questions"] == []
        assert data["sources"] == []
        assert data["facts"] == []
        assert data["phase"] == "scope"
        assert "created_at" in data

    def test_returns_state_path(self, research_file: Path):
        result = state.init_research(
            research_id="test-research",
            goal="Test",
            state_dir=research_file.parent,
        )
        assert result["state_file"] == str(research_file)

    def test_rejects_empty_goal(self, research_file: Path):
        with pytest.raises(ContractViolationError, match="(?i)goal"):
            state.init_research(
                research_id="x",
                goal="",
                state_dir=research_file.parent,
            )

    def test_rejects_empty_research_id(self, research_file: Path):
        with pytest.raises(ContractViolationError, match="(?i)research_id"):
            state.init_research(
                research_id="",
                goal="Something",
                state_dir=research_file.parent,
            )

    def test_resume_existing_does_not_overwrite(self, research_file: Path):
        state.init_research("test-research", "Goal A", state_dir=research_file.parent)
        state.add_questions("test-research", ["Q1"], state_dir=research_file.parent)
        # Re-init should NOT wipe existing data
        result = state.init_research("test-research", "Goal A", state_dir=research_file.parent)
        data = json.loads(research_file.read_text(encoding="utf-8"))
        assert len(data["questions"]) == 1
        assert result["resumed"] is True

    def test_custom_state_dir(self, tmp_path: Path):
        custom = tmp_path / "custom"
        result = state.init_research("r1", "Goal", state_dir=custom)
        assert (custom / "r1.json").exists()


# ---------------------------------------------------------------------------
# add_questions tests
# ---------------------------------------------------------------------------

class TestAddQuestions:
    def test_adds_questions(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        result = state.add_questions(
            "test-research",
            ["What is X?", "How does Y work?"],
            state_dir=research_file.parent,
        )
        data = json.loads(research_file.read_text(encoding="utf-8"))
        assert len(data["questions"]) == 2
        assert data["questions"][0]["text"] == "What is X?"
        assert data["questions"][0]["status"] == "unexplored"

    def test_deduplicates_questions(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        state.add_questions("test-research", ["Q1", "Q2"], state_dir=research_file.parent)
        state.add_questions("test-research", ["Q2", "Q3"], state_dir=research_file.parent)
        data = json.loads(research_file.read_text(encoding="utf-8"))
        texts = [q["text"] for q in data["questions"]]
        assert texts == ["Q1", "Q2", "Q3"]

    def test_rejects_empty_list(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        with pytest.raises(ContractViolationError, match="(?i)question"):
            state.add_questions("test-research", [], state_dir=research_file.parent)

    def test_returns_question_count(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        result = state.add_questions(
            "test-research", ["Q1"], state_dir=research_file.parent
        )
        assert result["total_questions"] == 1


# ---------------------------------------------------------------------------
# update_question tests
# ---------------------------------------------------------------------------

class TestUpdateQuestion:
    def test_marks_question_covered(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        state.add_questions("test-research", ["Q1"], state_dir=research_file.parent)
        state.update_question(
            "test-research", "Q1", status="covered", state_dir=research_file.parent
        )
        data = json.loads(research_file.read_text(encoding="utf-8"))
        assert data["questions"][0]["status"] == "covered"

    def test_marks_question_partially(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        state.add_questions("test-research", ["Q1"], state_dir=research_file.parent)
        state.update_question(
            "test-research", "Q1", status="partially", state_dir=research_file.parent
        )
        data = json.loads(research_file.read_text(encoding="utf-8"))
        assert data["questions"][0]["status"] == "partially"

    def test_rejects_unknown_question(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        state.add_questions("test-research", ["Q1"], state_dir=research_file.parent)
        with pytest.raises(ContractViolationError, match="(?i)not found"):
            state.update_question(
                "test-research", "NOPE", status="covered",
                state_dir=research_file.parent,
            )

    def test_rejects_invalid_status(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        state.add_questions("test-research", ["Q1"], state_dir=research_file.parent)
        with pytest.raises(ContractViolationError, match="(?i)status"):
            state.update_question(
                "test-research", "Q1", status="banana",
                state_dir=research_file.parent,
            )


# ---------------------------------------------------------------------------
# add_sources tests
# ---------------------------------------------------------------------------

class TestAddSources:
    def test_adds_sources(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        result = state.add_sources(
            "test-research",
            [{"url": "https://example.com/a", "title": "A", "skill": "duckduckgo"}],
            state_dir=research_file.parent,
        )
        data = json.loads(research_file.read_text(encoding="utf-8"))
        assert len(data["sources"]) == 1
        assert data["sources"][0]["url"] == "https://example.com/a"
        assert data["sources"][0]["skill"] == "duckduckgo"

    def test_deduplicates_by_url(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        state.add_sources(
            "test-research",
            [{"url": "https://example.com/a", "title": "A", "skill": "duckduckgo"}],
            state_dir=research_file.parent,
        )
        state.add_sources(
            "test-research",
            [
                {"url": "https://example.com/a", "title": "A dup", "skill": "duckduckgo"},
                {"url": "https://example.com/b", "title": "B", "skill": "drive"},
            ],
            state_dir=research_file.parent,
        )
        data = json.loads(research_file.read_text(encoding="utf-8"))
        assert len(data["sources"]) == 2

    def test_assigns_source_ids(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        state.add_sources(
            "test-research",
            [
                {"url": "https://a.com", "title": "A", "skill": "web"},
                {"url": "https://b.com", "title": "B", "skill": "web"},
            ],
            state_dir=research_file.parent,
        )
        data = json.loads(research_file.read_text(encoding="utf-8"))
        ids = [s["id"] for s in data["sources"]]
        assert ids == ["s1", "s2"]

    def test_rejects_empty_list(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        with pytest.raises(ContractViolationError, match="(?i)source"):
            state.add_sources("test-research", [], state_dir=research_file.parent)


# ---------------------------------------------------------------------------
# add_facts tests
# ---------------------------------------------------------------------------

class TestAddFacts:
    def test_adds_facts(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        state.add_sources(
            "test-research",
            [{"url": "https://a.com", "title": "A", "skill": "web"}],
            state_dir=research_file.parent,
        )
        result = state.add_facts(
            "test-research",
            [{"claim": "X is true", "source_ids": ["s1"], "confidence": "high"}],
            state_dir=research_file.parent,
        )
        data = json.loads(research_file.read_text(encoding="utf-8"))
        assert len(data["facts"]) == 1
        assert data["facts"][0]["claim"] == "X is true"
        assert data["facts"][0]["confidence"] == "high"

    def test_assigns_fact_ids(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        state.add_facts(
            "test-research",
            [
                {"claim": "A", "source_ids": [], "confidence": "medium"},
                {"claim": "B", "source_ids": [], "confidence": "low"},
            ],
            state_dir=research_file.parent,
        )
        data = json.loads(research_file.read_text(encoding="utf-8"))
        ids = [f["id"] for f in data["facts"]]
        assert ids == ["f1", "f2"]

    def test_appends_across_calls(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        state.add_facts(
            "test-research",
            [{"claim": "A", "source_ids": [], "confidence": "high"}],
            state_dir=research_file.parent,
        )
        state.add_facts(
            "test-research",
            [{"claim": "B", "source_ids": [], "confidence": "low"}],
            state_dir=research_file.parent,
        )
        data = json.loads(research_file.read_text(encoding="utf-8"))
        assert len(data["facts"]) == 2
        assert data["facts"][1]["id"] == "f2"

    def test_rejects_empty_list(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        with pytest.raises(ContractViolationError, match="(?i)fact"):
            state.add_facts("test-research", [], state_dir=research_file.parent)


# ---------------------------------------------------------------------------
# update_phase tests
# ---------------------------------------------------------------------------

class TestUpdatePhase:
    def test_updates_phase(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        state.update_phase("test-research", "sweep", state_dir=research_file.parent)
        data = json.loads(research_file.read_text(encoding="utf-8"))
        assert data["phase"] == "sweep"

    def test_rejects_invalid_phase(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        with pytest.raises(ContractViolationError, match="(?i)phase"):
            state.update_phase(
                "test-research", "invalid", state_dir=research_file.parent
            )


# ---------------------------------------------------------------------------
# get_status tests
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_returns_coverage_summary(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        state.add_questions("test-research", ["Q1", "Q2", "Q3"], state_dir=research_file.parent)
        state.update_question("test-research", "Q1", "covered", state_dir=research_file.parent)
        state.update_question("test-research", "Q2", "partially", state_dir=research_file.parent)
        status = state.get_status("test-research", state_dir=research_file.parent)
        assert status["total_questions"] == 3
        assert status["covered"] == 1
        assert status["partially"] == 1
        assert status["unexplored"] == 1

    def test_returns_source_and_fact_counts(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        state.add_sources(
            "test-research",
            [{"url": "https://a.com", "title": "A", "skill": "web"}],
            state_dir=research_file.parent,
        )
        state.add_facts(
            "test-research",
            [{"claim": "X", "source_ids": ["s1"], "confidence": "high"}],
            state_dir=research_file.parent,
        )
        status = state.get_status("test-research", state_dir=research_file.parent)
        assert status["total_sources"] == 1
        assert status["total_facts"] == 1

    def test_returns_current_phase(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        status = state.get_status("test-research", state_dir=research_file.parent)
        assert status["phase"] == "scope"

    def test_returns_goal(self, research_file: Path):
        state.init_research("test-research", "Goal text", state_dir=research_file.parent)
        status = state.get_status("test-research", state_dir=research_file.parent)
        assert status["goal"] == "Goal text"

    def test_nonexistent_research_errors(self, state_dir: Path):
        with pytest.raises(FileNotFoundError):
            state.get_status("nope", state_dir=state_dir)


# ---------------------------------------------------------------------------
# export tests
# ---------------------------------------------------------------------------

class TestExport:
    def test_exports_full_state(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        state.add_questions("test-research", ["Q1"], state_dir=research_file.parent)
        state.add_sources(
            "test-research",
            [{"url": "https://a.com", "title": "A", "skill": "web"}],
            state_dir=research_file.parent,
        )
        state.add_facts(
            "test-research",
            [{"claim": "X", "source_ids": ["s1"], "confidence": "high"}],
            state_dir=research_file.parent,
        )
        exported = state.export_research("test-research", state_dir=research_file.parent)
        assert exported["research_id"] == "test-research"
        assert len(exported["questions"]) == 1
        assert len(exported["sources"]) == 1
        assert len(exported["facts"]) == 1

    def test_export_is_json_serializable(self, research_file: Path):
        state.init_research("test-research", "Goal", state_dir=research_file.parent)
        exported = state.export_research("test-research", state_dir=research_file.parent)
        json.dumps(exported, ensure_ascii=False)


# ---------------------------------------------------------------------------
# _load / _save round-trip
# ---------------------------------------------------------------------------

class TestLoadSaveRoundTrip:
    def test_round_trip_preserves_data(self, research_file: Path):
        state.init_research("test-research", "Round trip test", state_dir=research_file.parent)
        state.add_questions("test-research", ["Q1", "Q2"], state_dir=research_file.parent)
        state.add_sources(
            "test-research",
            [{"url": "https://x.com", "title": "X", "skill": "skill-a"}],
            state_dir=research_file.parent,
        )
        state.add_facts(
            "test-research",
            [{"claim": "Claim A", "source_ids": ["s1"], "confidence": "high"}],
            state_dir=research_file.parent,
        )
        state.update_question("test-research", "Q1", "covered", state_dir=research_file.parent)
        state.update_phase("test-research", "deep-read", state_dir=research_file.parent)

        # Re-load and verify
        exported = state.export_research("test-research", state_dir=research_file.parent)
        assert exported["goal"] == "Round trip test"
        assert exported["phase"] == "deep-read"
        assert exported["questions"][0]["status"] == "covered"
        assert exported["questions"][1]["status"] == "unexplored"
        assert exported["sources"][0]["skill"] == "skill-a"
        assert exported["facts"][0]["claim"] == "Claim A"


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLI:
    def test_cli_init(self, state_dir: Path, capsys):
        state.main([
            "init", "--research-id", "cli-test", "--goal", "CLI goal",
            "--state-dir", str(state_dir),
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["research_id"] == "cli-test"

    def test_cli_add_questions(self, state_dir: Path, capsys):
        state.main([
            "init", "--research-id", "cli-q", "--goal", "Q goal",
            "--state-dir", str(state_dir),
        ])
        capsys.readouterr()
        state.main([
            "add-questions", "--research-id", "cli-q",
            "--questions", "Q1", "Q2",
            "--state-dir", str(state_dir),
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total_questions"] == 2

    def test_cli_add_questions_from_file(self, state_dir: Path, capsys, tmp_path: Path):
        state.main([
            "init", "--research-id", "cli-q-f", "--goal", "Q file goal",
            "--state-dir", str(state_dir),
        ])
        capsys.readouterr()
        json_file = tmp_path / "questions.json"
        json_file.write_text(json.dumps([
            "What is the impact of X on Y?",
            "How does A relate to B in context of C?",
            "What are the key\nmulti-line\nquestions?",
        ]), encoding="utf-8")
        state.main([
            "add-questions", "--research-id", "cli-q-f",
            "--file", str(json_file),
            "--state-dir", str(state_dir),
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total_questions"] == 3

    def test_cli_add_questions_from_stdin(self, state_dir: Path, capsys, monkeypatch):
        state.main([
            "init", "--research-id", "cli-q-stdin", "--goal", "Q stdin goal",
            "--state-dir", str(state_dir),
        ])
        capsys.readouterr()
        import io
        stdin_data = json.dumps(["Stdin question 1", "Stdin question 2"])
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin_data))
        state.main([
            "add-questions", "--research-id", "cli-q-stdin",
            "--file", "-",
            "--state-dir", str(state_dir),
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total_questions"] == 2

    def test_cli_add_questions_file_overrides_inline(self, state_dir: Path, capsys, tmp_path: Path):
        """When both --file and --questions are given, --file wins."""
        state.main([
            "init", "--research-id", "cli-q-both", "--goal", "Q both goal",
            "--state-dir", str(state_dir),
        ])
        capsys.readouterr()
        json_file = tmp_path / "questions_override.json"
        json_file.write_text(json.dumps([
            "File question 1",
            "File question 2",
            "File question 3",
        ]), encoding="utf-8")
        state.main([
            "add-questions", "--research-id", "cli-q-both",
            "--questions", "Inline Q",
            "--file", str(json_file),
            "--state-dir", str(state_dir),
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        # File has 3 questions, inline has 1 — file wins
        assert data["total_questions"] == 3

    def test_cli_update_question_from_file(self, state_dir: Path, capsys, tmp_path: Path):
        state.main([
            "init", "--research-id", "cli-uq-f", "--goal", "UQ file goal",
            "--state-dir", str(state_dir),
        ])
        capsys.readouterr()
        state.main([
            "add-questions", "--research-id", "cli-uq-f",
            "--questions", "What is the meaning of life?",
            "--state-dir", str(state_dir),
        ])
        capsys.readouterr()
        json_file = tmp_path / "update_q.json"
        json_file.write_text(json.dumps({
            "question": "What is the meaning of life?",
            "status": "covered",
        }), encoding="utf-8")
        state.main([
            "update-question", "--research-id", "cli-uq-f",
            "--status", "open",
            "--file", str(json_file),
            "--state-dir", str(state_dir),
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["question"] == "What is the meaning of life?"
        # --file status ("covered") wins over --status ("open")
        assert data["status"] == "covered"

    def test_cli_status(self, state_dir: Path, capsys):
        state.main([
            "init", "--research-id", "cli-s", "--goal", "S goal",
            "--state-dir", str(state_dir),
        ])
        capsys.readouterr()
        state.main([
            "status", "--research-id", "cli-s",
            "--state-dir", str(state_dir),
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "phase" in data

    def test_cli_export(self, state_dir: Path, capsys):
        state.main([
            "init", "--research-id", "cli-e", "--goal", "E goal",
            "--state-dir", str(state_dir),
        ])
        capsys.readouterr()
        state.main([
            "export", "--research-id", "cli-e",
            "--state-dir", str(state_dir),
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["research_id"] == "cli-e"

    def test_cli_add_sources(self, state_dir: Path, capsys):
        state.main([
            "init", "--research-id", "cli-src", "--goal", "Src goal",
            "--state-dir", str(state_dir),
        ])
        capsys.readouterr()
        state.main([
            "add-sources", "--research-id", "cli-src",
            "--sources", json.dumps([
                {"url": "https://a.com", "title": "A", "skill": "web"},
            ]),
            "--state-dir", str(state_dir),
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total_sources"] == 1

    def test_cli_add_sources_from_file(self, state_dir: Path, capsys, tmp_path: Path):
        state.main([
            "init", "--research-id", "cli-src-f", "--goal", "Src file goal",
            "--state-dir", str(state_dir),
        ])
        capsys.readouterr()
        json_file = tmp_path / "sources.json"
        json_file.write_text(json.dumps([
            {"url": "https://b.com", "title": "B", "skill": "drive"},
            {"url": "https://c.com", "title": "C", "skill": "web"},
        ]), encoding="utf-8")
        state.main([
            "add-sources", "--research-id", "cli-src-f",
            "--file", str(json_file),
            "--state-dir", str(state_dir),
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total_sources"] == 2

    def test_cli_add_facts(self, state_dir: Path, capsys):
        state.main([
            "init", "--research-id", "cli-fact", "--goal", "Fact goal",
            "--state-dir", str(state_dir),
        ])
        capsys.readouterr()
        state.main([
            "add-facts", "--research-id", "cli-fact",
            "--facts", json.dumps([
                {"claim": "X is Y", "source_ids": [], "confidence": "medium"},
            ]),
            "--state-dir", str(state_dir),
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total_facts"] == 1

    def test_cli_add_facts_from_file(self, state_dir: Path, capsys, tmp_path: Path):
        state.main([
            "init", "--research-id", "cli-fact-f", "--goal", "Fact file goal",
            "--state-dir", str(state_dir),
        ])
        capsys.readouterr()
        json_file = tmp_path / "facts.json"
        json_file.write_text(json.dumps([
            {"claim": "A causes B", "source_ids": ["s1"], "confidence": "high"},
            {"claim": "C implies D", "source_ids": ["s2"], "confidence": "low"},
        ]), encoding="utf-8")
        state.main([
            "add-facts", "--research-id", "cli-fact-f",
            "--file", str(json_file),
            "--state-dir", str(state_dir),
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total_facts"] == 2

    def test_cli_add_facts_from_stdin(self, state_dir: Path, capsys, monkeypatch):
        state.main([
            "init", "--research-id", "cli-fact-stdin", "--goal", "Stdin goal",
            "--state-dir", str(state_dir),
        ])
        capsys.readouterr()
        import io
        stdin_data = json.dumps([
            {"claim": "stdin fact", "source_ids": [], "confidence": "medium"},
        ])
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin_data))
        state.main([
            "add-facts", "--research-id", "cli-fact-stdin",
            "--file", "-",
            "--state-dir", str(state_dir),
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total_facts"] == 1

    def test_cli_add_facts_file_overrides_inline(self, state_dir: Path, capsys, tmp_path: Path):
        """When both --file and --facts are given, --file wins."""
        state.main([
            "init", "--research-id", "cli-fact-both", "--goal", "Both goal",
            "--state-dir", str(state_dir),
        ])
        capsys.readouterr()
        json_file = tmp_path / "facts_override.json"
        json_file.write_text(json.dumps([
            {"claim": "from file", "source_ids": [], "confidence": "high"},
            {"claim": "also from file", "source_ids": [], "confidence": "high"},
        ]), encoding="utf-8")
        state.main([
            "add-facts", "--research-id", "cli-fact-both",
            "--facts", json.dumps([{"claim": "from inline", "source_ids": [], "confidence": "low"}]),
            "--file", str(json_file),
            "--state-dir", str(state_dir),
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        # File has 2 facts, inline has 1 — file wins
        assert data["total_facts"] == 2

    def test_cli_update_phase(self, state_dir: Path, capsys):
        state.main([
            "init", "--research-id", "cli-ph", "--goal", "Phase goal",
            "--state-dir", str(state_dir),
        ])
        capsys.readouterr()
        state.main([
            "update-phase", "--research-id", "cli-ph",
            "--phase", "sweep",
            "--state-dir", str(state_dir),
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["phase"] == "sweep"
