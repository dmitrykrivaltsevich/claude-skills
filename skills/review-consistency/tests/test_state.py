"""Tests for state.py — review state CRUD with JSON persistence."""

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


@pytest.fixture
def review_file(state_dir: Path) -> Path:
    return state_dir / "test-review.json"


def _init(state_dir: Path, review_id: str = "test-review", scope: str = "Test scope"):
    return state.init_review(review_id, scope, state_dir=state_dir)


def _sample_chunks() -> list[dict]:
    return [
        {"path": "src/main.py", "size": 100, "hash": "sha256:aaa"},
        {"path": "src/utils.py", "size": 200, "hash": "sha256:bbb"},
        {"path": "docs/README.md", "size": 50, "hash": "sha256:ccc"},
    ]


# ---------------------------------------------------------------------------
# init_review tests
# ---------------------------------------------------------------------------


class TestInitReview:
    def test_creates_new_state_file(self, review_file: Path):
        _init(review_file.parent)
        assert review_file.exists()
        data = json.loads(review_file.read_text(encoding="utf-8"))
        assert data["review_id"] == "test-review"
        assert data["scope"] == "Test scope"
        assert data["phase"] == "inventory"
        assert data["chunks"] == []
        assert data["claims"] == []
        assert data["findings"] == []

    def test_returns_state_path(self, review_file: Path):
        result = _init(review_file.parent)
        assert result["state_file"] == str(review_file)
        assert result["resumed"] is False

    def test_resume_existing_does_not_overwrite(self, review_file: Path):
        _init(review_file.parent)
        state.add_chunks("test-review", _sample_chunks()[:1], state_dir=review_file.parent)
        result = _init(review_file.parent)
        data = json.loads(review_file.read_text(encoding="utf-8"))
        assert len(data["chunks"]) == 1
        assert result["resumed"] is True

    def test_rejects_empty_review_id(self, state_dir: Path):
        with pytest.raises(ContractViolationError, match="(?i)review_id"):
            state.init_review("", "scope", state_dir=state_dir)

    def test_rejects_empty_scope(self, state_dir: Path):
        with pytest.raises(ContractViolationError, match="(?i)scope"):
            state.init_review("id", "", state_dir=state_dir)


# ---------------------------------------------------------------------------
# add_chunks tests
# ---------------------------------------------------------------------------


class TestAddChunks:
    def test_adds_chunks(self, review_file: Path):
        _init(review_file.parent)
        result = state.add_chunks(
            "test-review", _sample_chunks(), state_dir=review_file.parent
        )
        data = json.loads(review_file.read_text(encoding="utf-8"))
        assert len(data["chunks"]) == 3
        assert data["chunks"][0]["id"] == "c1"
        assert data["chunks"][0]["path"] == "src/main.py"
        assert data["chunks"][0]["status"] == "unreviewed"
        assert result["total_chunks"] == 3

    def test_deduplicates_by_path(self, review_file: Path):
        _init(review_file.parent)
        state.add_chunks("test-review", _sample_chunks()[:2], state_dir=review_file.parent)
        state.add_chunks("test-review", _sample_chunks()[:2], state_dir=review_file.parent)
        data = json.loads(review_file.read_text(encoding="utf-8"))
        assert len(data["chunks"]) == 2

    def test_updates_hash_on_readd(self, review_file: Path):
        """When a chunk is re-added with a different hash, update it and reset status."""
        _init(review_file.parent)
        state.add_chunks(
            "test-review",
            [{"path": "a.py", "size": 10, "hash": "sha256:old"}],
            state_dir=review_file.parent,
        )
        state.update_chunk("test-review", "c1", "extracted", state_dir=review_file.parent)
        # Re-add with different hash — simulates file changed on disk
        state.add_chunks(
            "test-review",
            [{"path": "a.py", "size": 20, "hash": "sha256:new"}],
            state_dir=review_file.parent,
        )
        data = json.loads(review_file.read_text(encoding="utf-8"))
        assert data["chunks"][0]["hash"] == "sha256:new"
        assert data["chunks"][0]["size"] == 20
        # Status reset because content changed
        assert data["chunks"][0]["status"] == "unreviewed"

    def test_keeps_status_if_hash_unchanged(self, review_file: Path):
        _init(review_file.parent)
        state.add_chunks(
            "test-review",
            [{"path": "a.py", "size": 10, "hash": "sha256:same"}],
            state_dir=review_file.parent,
        )
        state.update_chunk("test-review", "c1", "extracted", state_dir=review_file.parent)
        state.add_chunks(
            "test-review",
            [{"path": "a.py", "size": 10, "hash": "sha256:same"}],
            state_dir=review_file.parent,
        )
        data = json.loads(review_file.read_text(encoding="utf-8"))
        assert data["chunks"][0]["status"] == "extracted"

    def test_rejects_empty_list(self, review_file: Path):
        _init(review_file.parent)
        with pytest.raises(ContractViolationError, match="(?i)chunk"):
            state.add_chunks("test-review", [], state_dir=review_file.parent)


# ---------------------------------------------------------------------------
# update_chunk tests
# ---------------------------------------------------------------------------


class TestUpdateChunk:
    def test_marks_chunk_extracted(self, review_file: Path):
        _init(review_file.parent)
        state.add_chunks("test-review", _sample_chunks()[:1], state_dir=review_file.parent)
        state.update_chunk("test-review", "c1", "extracted", state_dir=review_file.parent)
        data = json.loads(review_file.read_text(encoding="utf-8"))
        assert data["chunks"][0]["status"] == "extracted"

    def test_marks_chunk_reviewed(self, review_file: Path):
        _init(review_file.parent)
        state.add_chunks("test-review", _sample_chunks()[:1], state_dir=review_file.parent)
        result = state.update_chunk(
            "test-review", "c1", "reviewed", state_dir=review_file.parent
        )
        assert result["chunk_id"] == "c1"
        assert result["status"] == "reviewed"

    def test_rejects_unknown_chunk(self, review_file: Path):
        _init(review_file.parent)
        state.add_chunks("test-review", _sample_chunks()[:1], state_dir=review_file.parent)
        with pytest.raises(ContractViolationError, match="(?i)not found"):
            state.update_chunk(
                "test-review", "c999", "extracted", state_dir=review_file.parent
            )

    def test_rejects_invalid_status(self, review_file: Path):
        _init(review_file.parent)
        state.add_chunks("test-review", _sample_chunks()[:1], state_dir=review_file.parent)
        with pytest.raises(ContractViolationError, match="(?i)status"):
            state.update_chunk(
                "test-review", "c1", "banana", state_dir=review_file.parent
            )


# ---------------------------------------------------------------------------
# add_claims tests
# ---------------------------------------------------------------------------


class TestAddClaims:
    def test_adds_claims(self, review_file: Path):
        _init(review_file.parent)
        state.add_chunks("test-review", _sample_chunks()[:1], state_dir=review_file.parent)
        result = state.add_claims(
            "test-review",
            [
                {"chunk_id": "c1", "text": "function foo returns string", "category": "contract", "location": "line 10"},
                {"chunk_id": "c1", "text": "all errors logged to stderr", "category": "convention", "location": "line 20"},
            ],
            state_dir=review_file.parent,
        )
        data = json.loads(review_file.read_text(encoding="utf-8"))
        assert len(data["claims"]) == 2
        assert data["claims"][0]["id"] == "cl1"
        assert data["claims"][0]["chunk_id"] == "c1"
        assert result["total_claims"] == 2

    def test_rejects_empty_list(self, review_file: Path):
        _init(review_file.parent)
        with pytest.raises(ContractViolationError, match="(?i)claim"):
            state.add_claims("test-review", [], state_dir=review_file.parent)

    def test_rejects_invalid_category(self, review_file: Path):
        _init(review_file.parent)
        with pytest.raises(ContractViolationError, match="(?i)category"):
            state.add_claims(
                "test-review",
                [{"chunk_id": "c1", "text": "x", "category": "banana", "location": "line 1"}],
                state_dir=review_file.parent,
            )


# ---------------------------------------------------------------------------
# add_findings tests
# ---------------------------------------------------------------------------


class TestAddFindings:
    def _sample_finding(self, **overrides) -> dict:
        base = {
            "fingerprint": "fp1",
            "class": "internal-contradiction",
            "severity": "critical",
            "title": "Return type mismatch",
            "where": "src/main.py:10, src/utils.py:20",
            "what": "Signature says string, returns int",
            "why": "Runtime error for callers expecting string",
            "suggestion": "Fix return type",
            "chunk_ids": ["c1", "c2"],
            "claim_ids": ["cl1", "cl2"],
        }
        base.update(overrides)
        return base

    def test_adds_finding(self, review_file: Path):
        _init(review_file.parent)
        result = state.add_findings(
            "test-review",
            [self._sample_finding()],
            state_dir=review_file.parent,
        )
        data = json.loads(review_file.read_text(encoding="utf-8"))
        assert len(data["findings"]) == 1
        assert data["findings"][0]["id"] == "f1"
        assert data["findings"][0]["status"] == "open"
        assert result["total_findings"] == 1

    def test_deduplicates_by_fingerprint(self, review_file: Path):
        _init(review_file.parent)
        state.add_findings(
            "test-review",
            [self._sample_finding(fingerprint="fp1")],
            state_dir=review_file.parent,
        )
        state.add_findings(
            "test-review",
            [self._sample_finding(fingerprint="fp1", title="Updated title")],
            state_dir=review_file.parent,
        )
        data = json.loads(review_file.read_text(encoding="utf-8"))
        assert len(data["findings"]) == 1
        # Title should NOT update — existing finding is authoritative
        assert data["findings"][0]["title"] == "Return type mismatch"

    def test_adds_different_fingerprints(self, review_file: Path):
        _init(review_file.parent)
        state.add_findings(
            "test-review",
            [
                self._sample_finding(fingerprint="fp1"),
                self._sample_finding(fingerprint="fp2", title="Another issue"),
            ],
            state_dir=review_file.parent,
        )
        data = json.loads(review_file.read_text(encoding="utf-8"))
        assert len(data["findings"]) == 2

    def test_rejects_empty_list(self, review_file: Path):
        _init(review_file.parent)
        with pytest.raises(ContractViolationError, match="(?i)finding"):
            state.add_findings("test-review", [], state_dir=review_file.parent)

    def test_rejects_invalid_severity(self, review_file: Path):
        _init(review_file.parent)
        with pytest.raises(ContractViolationError, match="(?i)severity"):
            state.add_findings(
                "test-review",
                [self._sample_finding(severity="banana")],
                state_dir=review_file.parent,
            )
    def test_rejects_invalid_class(self, review_file: Path):
        _init(review_file.parent)
        with pytest.raises(ContractViolationError, match="(?i)class"):
            state.add_findings(
                "test-review",
                [self._sample_finding(**{"class": "banana"})],
                state_dir=review_file.parent,
            )

# ---------------------------------------------------------------------------
# update_finding tests
# ---------------------------------------------------------------------------


class TestUpdateFinding:
    def test_marks_finding_fixed(self, review_file: Path):
        _init(review_file.parent)
        state.add_findings(
            "test-review",
            [{"fingerprint": "fp1", "class": "internal-contradiction",
              "severity": "critical", "title": "Bug", "where": "a.py",
              "what": "bad", "why": "breaks", "suggestion": "fix",
              "chunk_ids": [], "claim_ids": []}],
            state_dir=review_file.parent,
        )
        result = state.update_finding(
            "test-review", "f1", "fixed", state_dir=review_file.parent
        )
        data = json.loads(review_file.read_text(encoding="utf-8"))
        assert data["findings"][0]["status"] == "fixed"
        assert result["finding_id"] == "f1"

    def test_rejects_unknown_finding(self, review_file: Path):
        _init(review_file.parent)
        with pytest.raises(ContractViolationError, match="(?i)not found"):
            state.update_finding(
                "test-review", "f999", "fixed", state_dir=review_file.parent
            )

    def test_rejects_invalid_status(self, review_file: Path):
        _init(review_file.parent)
        state.add_findings(
            "test-review",
            [{"fingerprint": "fp1", "class": "internal-contradiction", "severity": "critical",
              "title": "t", "where": "w", "what": "x", "why": "y",
              "suggestion": "s", "chunk_ids": [], "claim_ids": []}],
            state_dir=review_file.parent,
        )
        with pytest.raises(ContractViolationError, match="(?i)status"):
            state.update_finding(
                "test-review", "f1", "banana", state_dir=review_file.parent
            )


# ---------------------------------------------------------------------------
# pending tests
# ---------------------------------------------------------------------------


class TestPending:
    def test_returns_unreviewed_chunks(self, review_file: Path):
        _init(review_file.parent)
        state.add_chunks("test-review", _sample_chunks(), state_dir=review_file.parent)
        result = state.pending("test-review", state_dir=review_file.parent)
        assert result["unreviewed_chunks"] == 3
        assert result["unextracted_chunks"] == 3
        assert len(result["next_chunks"]) == 3

    def test_unreviewed_includes_extracted(self, review_file: Path):
        """unreviewed_chunks counts both unextracted AND extracted (not yet cross-checked)."""
        _init(review_file.parent)
        state.add_chunks("test-review", _sample_chunks(), state_dir=review_file.parent)
        state.update_chunk("test-review", "c1", "extracted", state_dir=review_file.parent)
        result = state.pending("test-review", state_dir=review_file.parent)
        # c1 is extracted but not reviewed — still counts as unreviewed
        assert result["unreviewed_chunks"] == 3
        # only c2 and c3 need extraction
        assert result["unextracted_chunks"] == 2

    def test_unextracted_and_unreviewed_differ(self, review_file: Path):
        """After extracting some chunks, unextracted < unreviewed."""
        _init(review_file.parent)
        state.add_chunks("test-review", _sample_chunks(), state_dir=review_file.parent)
        state.update_chunk("test-review", "c1", "extracted", state_dir=review_file.parent)
        state.update_chunk("test-review", "c2", "extracted", state_dir=review_file.parent)
        result = state.pending("test-review", state_dir=review_file.parent)
        assert result["unextracted_chunks"] == 1
        assert result["unreviewed_chunks"] == 3
        assert result["extracted_not_reviewed"] == 2

    def test_next_chunks_prioritizes_unextracted(self, review_file: Path):
        """next_chunks lists unextracted first, then extracted-not-reviewed."""
        _init(review_file.parent)
        state.add_chunks("test-review", _sample_chunks(), state_dir=review_file.parent)
        state.update_chunk("test-review", "c1", "extracted", state_dir=review_file.parent)
        result = state.pending("test-review", state_dir=review_file.parent)
        next_ids = [c["id"] for c in result["next_chunks"]]
        # c2, c3 (unextracted) come before c1 (extracted)
        assert next_ids == ["c2", "c3", "c1"]

    def test_reviewed_chunks_excluded_from_next(self, review_file: Path):
        _init(review_file.parent)
        state.add_chunks("test-review", _sample_chunks(), state_dir=review_file.parent)
        state.update_chunk("test-review", "c1", "reviewed", state_dir=review_file.parent)
        result = state.pending("test-review", state_dir=review_file.parent)
        next_ids = [c["id"] for c in result["next_chunks"]]
        assert "c1" not in next_ids
        assert result["unreviewed_chunks"] == 2

    def test_limit_parameter(self, review_file: Path):
        _init(review_file.parent)
        state.add_chunks("test-review", _sample_chunks(), state_dir=review_file.parent)
        result = state.pending("test-review", limit=1, state_dir=review_file.parent)
        assert len(result["next_chunks"]) == 1


# ---------------------------------------------------------------------------
# update_phase tests
# ---------------------------------------------------------------------------


class TestUpdatePhase:
    def test_advances_phase(self, review_file: Path):
        _init(review_file.parent)
        result = state.update_phase(
            "test-review", "extract", state_dir=review_file.parent
        )
        data = json.loads(review_file.read_text(encoding="utf-8"))
        assert data["phase"] == "extract"
        assert result["phase"] == "extract"

    def test_rejects_invalid_phase(self, review_file: Path):
        _init(review_file.parent)
        with pytest.raises(ContractViolationError, match="(?i)phase"):
            state.update_phase(
                "test-review", "banana", state_dir=review_file.parent
            )


# ---------------------------------------------------------------------------
# status tests
# ---------------------------------------------------------------------------


class TestStatus:
    def test_returns_summary(self, review_file: Path):
        _init(review_file.parent)
        state.add_chunks("test-review", _sample_chunks(), state_dir=review_file.parent)
        state.update_chunk("test-review", "c1", "extracted", state_dir=review_file.parent)
        state.add_claims(
            "test-review",
            [{"chunk_id": "c1", "text": "claim1", "category": "contract", "location": "line 1"}],
            state_dir=review_file.parent,
        )
        state.add_findings(
            "test-review",
            [{"fingerprint": "fp1", "class": "internal-contradiction", "severity": "critical",
              "title": "t", "where": "w", "what": "x", "why": "y",
              "suggestion": "s", "chunk_ids": [], "claim_ids": []}],
            state_dir=review_file.parent,
        )
        result = state.get_status("test-review", state_dir=review_file.parent)
        assert result["review_id"] == "test-review"
        assert result["phase"] == "inventory"
        assert result["total_chunks"] == 3
        assert result["extracted_chunks"] == 1
        assert result["reviewed_chunks"] == 0
        assert result["unreviewed_chunks"] == 2
        assert result["total_claims"] == 1
        assert result["total_findings"] == 1
        assert result["open_findings"] == 1


# ---------------------------------------------------------------------------
# export tests
# ---------------------------------------------------------------------------


class TestExport:
    def test_returns_full_state(self, review_file: Path):
        _init(review_file.parent)
        state.add_chunks("test-review", _sample_chunks()[:1], state_dir=review_file.parent)
        result = state.export_review("test-review", state_dir=review_file.parent)
        assert result["review_id"] == "test-review"
        assert "chunks" in result
        assert "claims" in result
        assert "findings" in result


# ---------------------------------------------------------------------------
# purge_stale_claims tests
# ---------------------------------------------------------------------------


class TestPurgeStaleClaims:
    def test_removes_claims_for_changed_chunks(self, review_file: Path):
        """When a chunk's hash changes, its old claims should be purgeable."""
        _init(review_file.parent)
        state.add_chunks(
            "test-review",
            [{"path": "a.py", "size": 10, "hash": "sha256:v1"}],
            state_dir=review_file.parent,
        )
        state.add_claims(
            "test-review",
            [{"chunk_id": "c1", "text": "old claim", "category": "contract", "location": "line 1"}],
            state_dir=review_file.parent,
        )
        # Simulate file change — re-add with new hash, which resets chunk to unreviewed
        state.add_chunks(
            "test-review",
            [{"path": "a.py", "size": 20, "hash": "sha256:v2"}],
            state_dir=review_file.parent,
        )
        result = state.purge_stale_claims("test-review", state_dir=review_file.parent)
        data = json.loads(review_file.read_text(encoding="utf-8"))
        # Claims for unreviewed chunks should be purged
        assert len(data["claims"]) == 0
        assert result["purged_claims"] == 1
