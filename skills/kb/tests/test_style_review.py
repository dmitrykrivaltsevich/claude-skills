"""Tests for style_review.py — KB review-record storage for style findings."""

from __future__ import annotations

import json

import pytest

from ._loader import load_script_module

try:
    _style_review = load_script_module("kb_test_style_review", "style_review.py")
except Exception as exc:  # red phase: module is not implemented yet
    _style_review = None
    _style_review_load_error = exc


@pytest.fixture
def sr():
    if _style_review is None:
        pytest.fail(f"style_review.py is not importable: {_style_review_load_error}")
    return _style_review


def _review_dir(kb_path):
    return kb_path / ".kb" / "style-reviewed"


def _key(file: str, line: int, pattern: str, match: str) -> dict:
    return {
        "file": file,
        "line": line,
        "pattern": pattern,
        "match": match,
    }


class TestAddReview:
    def test_add_creates_record(self, sr, tmp_path):
        kb = tmp_path / "kb"
        record = sr.add_review(
            str(kb),
            "knowledge/topics/slop.md",
            3,
            "crucially",
            "crucially",
            reason="other",
        )
        assert record["key"] == _key("knowledge/topics/slop.md", 3, "crucially", "crucially")
        assert record["reason"] == "other"
        assert "created" in record
        files = list(_review_dir(kb).glob("*.json"))
        assert len(files) == 1
        on_disk = json.loads(files[0].read_text(encoding="utf-8"))
        assert on_disk["key"] == record["key"]
        assert on_disk["reason"] == "other"

    def test_add_is_idempotent(self, sr, tmp_path):
        kb = tmp_path / "kb"
        first = sr.add_review(
            str(kb),
            "knowledge/topics/slop.md",
            3,
            "crucially",
            "crucially",
            reason="other",
        )
        second = sr.add_review(
            str(kb),
            "knowledge/topics/slop.md",
            3,
            "crucially",
            "crucially",
            reason="other",
        )
        assert first["key"] == second["key"]
        assert len(list(_review_dir(kb).glob("*.json"))) == 1

    def test_add_multiple_reviews(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_review(str(kb), "knowledge/a.md", 1, "crucially", "crucially", reason="other")
        sr.add_review(str(kb), "knowledge/a.md", 5, "seamless", "seamless", reason="other")
        sr.add_review(str(kb), "knowledge/b.md", 2, "pivotal", "pivotal", reason="other")
        assert len(list(_review_dir(kb).glob("*.json"))) == 3

    def test_add_stores_optional_note(self, sr, tmp_path):
        kb = tmp_path / "kb"
        record = sr.add_review(
            str(kb),
            "knowledge/topics/slop.md",
            3,
            "crucially",
            "crucially",
            reason="subject-matter",
            note="Domain-specific usage",
        )
        assert record["note"] == "Domain-specific usage"
        files = list(_review_dir(kb).glob("*.json"))
        on_disk = json.loads(files[0].read_text(encoding="utf-8"))
        assert on_disk["note"] == "Domain-specific usage"

    def test_add_without_note_omits_note(self, sr, tmp_path):
        kb = tmp_path / "kb"
        record = sr.add_review(
            str(kb),
            "knowledge/topics/slop.md",
            3,
            "crucially",
            "crucially",
            reason="other",
        )
        assert "note" not in record

    def test_add_accepts_all_allowed_reasons(self, sr, tmp_path):
        kb = tmp_path / "kb"
        for offset, reason in enumerate(("subject-matter", "verbatim-quote", "other")):
            sr.add_review(
                str(kb),
                "knowledge/a.md",
                offset + 1,
                "crucially",
                f"crucially-{offset}",
                reason=reason,
            )
        assert len(sr.list_reviews(str(kb))) == 3

    def test_add_rejects_invalid_reason(self, sr, tmp_path):
        kb = tmp_path / "kb"
        with pytest.raises(sr.ContractViolationError):
            sr.add_review(
                str(kb),
                "knowledge/a.md",
                1,
                "crucially",
                "crucially",
                reason="be-cause",
            )

    def test_add_rejects_non_positive_line(self, sr, tmp_path):
        kb = tmp_path / "kb"
        with pytest.raises(sr.ContractViolationError):
            sr.add_review(str(kb), "knowledge/a.md", 0, "crucially", "crucially", reason="other")
        with pytest.raises(sr.ContractViolationError):
            sr.add_review(str(kb), "knowledge/a.md", -1, "crucially", "crucially", reason="other")

    def test_add_rejects_empty_identity_fields(self, sr, tmp_path):
        kb = tmp_path / "kb"
        with pytest.raises(sr.ContractViolationError):
            sr.add_review(str(kb), "", 1, "crucially", "crucially", reason="other")
        with pytest.raises(sr.ContractViolationError):
            sr.add_review(str(kb), "a.md", 1, "", "crucially", reason="other")
        with pytest.raises(sr.ContractViolationError):
            sr.add_review(str(kb), "a.md", 1, "crucially", "", reason="other")


class TestNoteContract:
    def test_add_rejects_non_string_note(self, sr, tmp_path):
        kb = tmp_path / "kb"
        with pytest.raises(sr.ContractViolationError, match="note must be a string"):
            sr.add_review(
                str(kb), "knowledge/a.md", 1, "crucially", "crucially",
                reason="other", note=42,
            )
        assert not _review_dir(kb).exists()


class TestPathNormalization:
    def test_absolute_path_stored_as_kb_relative(self, sr, tmp_path):
        kb = tmp_path / "kb"
        kb.mkdir()
        record = sr.add_review(
            str(kb), str(kb / "knowledge" / "a.md"), 1, "crucially", "crucially", reason="other",
        )
        assert record["key"]["file"] == "knowledge/a.md"

    def test_backslash_and_dot_slash_normalized(self, sr, tmp_path):
        kb = tmp_path / "kb"
        first = sr.add_review(str(kb), "./knowledge/a.md", 1, "crucially", "crucially", reason="other")
        second = sr.add_review(str(kb), "knowledge\\a.md", 1, "crucially", "crucially", reason="other")
        assert first["key"]["file"] == "knowledge/a.md"
        assert second["key"]["file"] == "knowledge/a.md"
        assert len(sr.list_reviews(str(kb))) == 1

    def test_path_outside_kb_rejected(self, sr, tmp_path):
        kb = tmp_path / "kb"
        kb.mkdir()
        with pytest.raises(sr.ContractViolationError, match="(?i)inside the KB"):
            sr.add_review(str(kb), "../outside.md", 1, "crucially", "crucially", reason="other")
        with pytest.raises(sr.ContractViolationError, match="(?i)inside the KB"):
            sr.add_review(str(kb), "/etc/hosts", 1, "crucially", "crucially", reason="other")

    def test_remove_matches_normalized_key(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_review(str(kb), "knowledge/a.md", 1, "crucially", "crucially", reason="other")
        assert sr.remove_review(str(kb), "./knowledge/a.md", 1, "crucially", "crucially") is True


class TestKbPathIsFile:
    def test_add_rejects_file_as_kb_path(self, sr, tmp_path):
        not_a_dir = tmp_path / "kb.md"
        not_a_dir.write_text("not a directory\n", encoding="utf-8")
        with pytest.raises(sr.ContractViolationError, match="(?i)director"):
            sr.add_review(str(not_a_dir), "knowledge/a.md", 1, "crucially", "crucially", reason="other")

    def test_list_rejects_file_as_kb_path(self, sr, tmp_path):
        not_a_dir = tmp_path / "kb.md"
        not_a_dir.write_text("not a directory\n", encoding="utf-8")
        with pytest.raises(sr.ContractViolationError, match="(?i)director"):
            sr.list_reviews(str(not_a_dir))

    def test_cli_file_as_kb_path_exits_nonzero(self, sr, tmp_path, capsys):
        not_a_dir = tmp_path / "kb.md"
        not_a_dir.write_text("not a directory\n", encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            sr.main([
                "add", "--kb", str(not_a_dir), "--file", "knowledge/a.md", "--line", "1",
                "--pattern", "crucially", "--match", "crucially", "--reason", "other",
            ])
        assert exc_info.value.code == 1
        assert "error" in json.loads(capsys.readouterr().err)


class TestListReviews:
    def test_list_empty(self, sr, tmp_path):
        kb = tmp_path / "kb"
        assert sr.list_reviews(str(kb)) == []

    def test_list_sorted(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_review(str(kb), "knowledge/b.md", 2, "crucially", "crucially", reason="other")
        sr.add_review(str(kb), "knowledge/a.md", 10, "pivotal", "pivotal", reason="other")
        sr.add_review(str(kb), "knowledge/b.md", 1, "seamless", "seamless", reason="other")
        records = sr.list_reviews(str(kb))
        assert [(r["key"]["file"], r["key"]["line"]) for r in records] == [
            ("knowledge/a.md", 10),
            ("knowledge/b.md", 1),
            ("knowledge/b.md", 2),
        ]

    def test_load_review_records_exposes_canonical_tuples(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_review(str(kb), "knowledge/a.md", 3, "crucially", "crucially", reason="other")
        records = sr.load_review_records(str(kb))
        assert records[("knowledge/a.md", 3, "crucially", "crucially")]["reason"] == "other"

    def test_list_rejects_invalid_json(self, sr, tmp_path):
        kb = tmp_path / "kb"
        d = _review_dir(kb)
        d.mkdir(parents=True)
        (d / "bad.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(sr.ContractViolationError):
            sr.list_reviews(str(kb))

    def test_list_rejects_missing_fields(self, sr, tmp_path):
        kb = tmp_path / "kb"
        d = _review_dir(kb)
        d.mkdir(parents=True)
        (d / "bad.json").write_text(
            json.dumps({"key": {"file": "a.md", "line": 1, "pattern": "p", "match": "m"}}),
            encoding="utf-8",
        )
        with pytest.raises(sr.ContractViolationError):
            sr.list_reviews(str(kb))


class TestHandWrittenRecords:
    def test_non_canonical_path_rejected_on_read(self, sr, tmp_path):
        """A hand-written './x.md' key could never match a finding — fail loudly."""
        kb = tmp_path / "kb"
        review_dir = _review_dir(kb)
        review_dir.mkdir(parents=True)
        (review_dir / "manual.json").write_text(
            json.dumps({
                "schema": "kb-style-review/v1",
                "key": _key("./knowledge/a.md", 1, "crucially", "crucially"),
                "reason": "other",
                "created": "2026-01-01T00:00:00+00:00",
            }),
            encoding="utf-8",
        )
        with pytest.raises(sr.ContractViolationError, match="(?i)canonical"):
            sr.list_reviews(str(kb))


class TestRemoveReview:
    def test_remove_existing(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_review(str(kb), "knowledge/a.md", 1, "crucially", "crucially", reason="other")
        assert sr.remove_review(str(kb), "knowledge/a.md", 1, "crucially", "crucially") is True
        assert list(_review_dir(kb).glob("*.json")) == []

    def test_remove_missing_returns_false(self, sr, tmp_path):
        kb = tmp_path / "kb"
        assert sr.remove_review(str(kb), "knowledge/a.md", 1, "crucially", "crucially") is False


class TestAtomicity:
    def test_add_leaves_no_temp_files(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_review(str(kb), "knowledge/a.md", 1, "crucially", "crucially", reason="other")
        d = _review_dir(kb)
        assert list(d.glob("*.json"))
        assert not [p for p in d.iterdir() if p.name.startswith(".")]

class TestCli:
    def test_cli_add_list_remove_roundtrip(self, sr, tmp_path, capsys):
        kb = tmp_path / "kb"
        kb.mkdir()
        sr.main([
            "add", "--kb", str(kb), "--file", "knowledge/a.md", "--line", "12",
            "--pattern", "crucially", "--match", "crucially",
            "--reason", "verbatim-quote", "--note", "quoted from the source",
        ])
        added = json.loads(capsys.readouterr().out)
        assert added["key"] == _key("knowledge/a.md", 12, "crucially", "crucially")
        assert added["reason"] == "verbatim-quote"
        assert added["note"] == "quoted from the source"

        sr.main(["list", "--kb", str(kb)])
        listed = json.loads(capsys.readouterr().out)
        assert len(listed) == 1
        assert listed[0]["key"]["line"] == 12

        sr.main([
            "remove", "--kb", str(kb), "--file", "knowledge/a.md", "--line", "12",
            "--pattern", "crucially", "--match", "crucially",
        ])
        assert json.loads(capsys.readouterr().out) == {"removed": True}

    def test_cli_invalid_line_exits_nonzero(self, sr, tmp_path, capsys):
        kb = tmp_path / "kb"
        kb.mkdir()
        with pytest.raises(SystemExit) as exc_info:
            sr.main([
                "add", "--kb", str(kb), "--file", "knowledge/a.md", "--line", "0",
                "--pattern", "crucially", "--match", "crucially", "--reason", "other",
            ])
        assert exc_info.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert "positive integer" in err["error"]

    def test_cli_list_invalid_record_exits_nonzero(self, sr, tmp_path, capsys):
        kb = tmp_path / "kb"
        review_dir = _review_dir(kb)
        review_dir.mkdir(parents=True)
        (review_dir / "bad.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            sr.main(["list", "--kb", str(kb)])
        assert exc_info.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert "bad.json" in err["error"]
