"""Tests for style_exceptions.py — storage for accepted style-phrase exceptions."""

from __future__ import annotations

import json

import pytest

from ._loader import load_script_module

try:
    _style_exceptions = load_script_module("kb_test_style_exceptions", "style_exceptions.py")
except Exception as exc:  # red phase: module is not implemented yet
    _style_exceptions = None
    _style_exceptions_load_error = exc


@pytest.fixture
def sr():
    if _style_exceptions is None:
        pytest.fail(f"style_exceptions.py is not importable: {_style_exceptions_load_error}")
    return _style_exceptions


def _exception_dir(kb_path):
    return kb_path / ".kb" / "style-exceptions"


def _key(file: str, line: int, pattern: str, match: str) -> dict:
    return {
        "file": file,
        "line": line,
        "pattern": pattern,
        "match": match,
    }


class TestAddException:
    def test_add_creates_record(self, sr, tmp_path):
        kb = tmp_path / "kb"
        record = sr.add_exception(
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
        files = list(_exception_dir(kb).glob("*.json"))
        assert len(files) == 1
        on_disk = json.loads(files[0].read_text(encoding="utf-8"))
        assert on_disk["key"] == record["key"]
        assert on_disk["reason"] == "other"

    def test_add_is_idempotent(self, sr, tmp_path):
        kb = tmp_path / "kb"
        first = sr.add_exception(
            str(kb),
            "knowledge/topics/slop.md",
            3,
            "crucially",
            "crucially",
            reason="other",
        )
        second = sr.add_exception(
            str(kb),
            "knowledge/topics/slop.md",
            3,
            "crucially",
            "crucially",
            reason="other",
        )
        assert first["key"] == second["key"]
        assert len(list(_exception_dir(kb).glob("*.json"))) == 1

    def test_add_multiple_exceptions(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_exception(str(kb), "knowledge/a.md", 1, "crucially", "crucially", reason="other")
        sr.add_exception(str(kb), "knowledge/a.md", 5, "seamless", "seamless", reason="other")
        sr.add_exception(str(kb), "knowledge/b.md", 2, "pivotal", "pivotal", reason="other")
        assert len(list(_exception_dir(kb).glob("*.json"))) == 3

    def test_add_stores_optional_note(self, sr, tmp_path):
        kb = tmp_path / "kb"
        record = sr.add_exception(
            str(kb),
            "knowledge/topics/slop.md",
            3,
            "crucially",
            "crucially",
            reason="subject-matter",
            note="Domain-specific usage",
        )
        assert record["note"] == "Domain-specific usage"
        files = list(_exception_dir(kb).glob("*.json"))
        on_disk = json.loads(files[0].read_text(encoding="utf-8"))
        assert on_disk["note"] == "Domain-specific usage"

    def test_add_without_note_omits_note(self, sr, tmp_path):
        kb = tmp_path / "kb"
        record = sr.add_exception(
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
            sr.add_exception(
                str(kb),
                "knowledge/a.md",
                offset + 1,
                "crucially",
                f"crucially-{offset}",
                reason=reason,
            )
        assert len(sr.list_exceptions(str(kb))) == 3

    def test_add_rejects_invalid_reason(self, sr, tmp_path):
        kb = tmp_path / "kb"
        with pytest.raises(sr.ContractViolationError):
            sr.add_exception(
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
            sr.add_exception(str(kb), "knowledge/a.md", 0, "crucially", "crucially", reason="other")
        with pytest.raises(sr.ContractViolationError):
            sr.add_exception(str(kb), "knowledge/a.md", -1, "crucially", "crucially", reason="other")

    def test_add_rejects_empty_identity_fields(self, sr, tmp_path):
        kb = tmp_path / "kb"
        with pytest.raises(sr.ContractViolationError):
            sr.add_exception(str(kb), "", 1, "crucially", "crucially", reason="other")
        with pytest.raises(sr.ContractViolationError):
            sr.add_exception(str(kb), "a.md", 1, "", "crucially", reason="other")
        with pytest.raises(sr.ContractViolationError):
            sr.add_exception(str(kb), "a.md", 1, "crucially", "", reason="other")


class TestNoteContract:
    def test_add_rejects_non_string_note(self, sr, tmp_path):
        kb = tmp_path / "kb"
        with pytest.raises(sr.ContractViolationError, match="note must be a string"):
            sr.add_exception(
                str(kb), "knowledge/a.md", 1, "crucially", "crucially",
                reason="other", note=42,
            )
        assert not _exception_dir(kb).exists()


class TestPathNormalization:
    def test_absolute_path_stored_as_kb_relative(self, sr, tmp_path):
        kb = tmp_path / "kb"
        kb.mkdir()
        record = sr.add_exception(
            str(kb), str(kb / "knowledge" / "a.md"), 1, "crucially", "crucially", reason="other",
        )
        assert record["key"]["file"] == "knowledge/a.md"

    def test_backslash_and_dot_slash_normalized(self, sr, tmp_path):
        kb = tmp_path / "kb"
        first = sr.add_exception(str(kb), "./knowledge/a.md", 1, "crucially", "crucially", reason="other")
        second = sr.add_exception(str(kb), "knowledge\\a.md", 1, "crucially", "crucially", reason="other")
        assert first["key"]["file"] == "knowledge/a.md"
        assert second["key"]["file"] == "knowledge/a.md"
        assert len(sr.list_exceptions(str(kb))) == 1

    def test_path_outside_kb_rejected(self, sr, tmp_path):
        kb = tmp_path / "kb"
        kb.mkdir()
        with pytest.raises(sr.ContractViolationError, match="(?i)inside the KB"):
            sr.add_exception(str(kb), "../outside.md", 1, "crucially", "crucially", reason="other")
        with pytest.raises(sr.ContractViolationError, match="(?i)inside the KB"):
            sr.add_exception(str(kb), "/etc/hosts", 1, "crucially", "crucially", reason="other")

    def test_remove_matches_normalized_key(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_exception(str(kb), "knowledge/a.md", 1, "crucially", "crucially", reason="other")
        assert sr.remove_exception(str(kb), "./knowledge/a.md", 1, "crucially", "crucially") is True


class TestKbPathIsFile:
    def test_add_rejects_file_as_kb_path(self, sr, tmp_path):
        not_a_dir = tmp_path / "kb.md"
        not_a_dir.write_text("not a directory\n", encoding="utf-8")
        with pytest.raises(sr.ContractViolationError, match="(?i)director"):
            sr.add_exception(str(not_a_dir), "knowledge/a.md", 1, "crucially", "crucially", reason="other")

    def test_list_rejects_file_as_kb_path(self, sr, tmp_path):
        not_a_dir = tmp_path / "kb.md"
        not_a_dir.write_text("not a directory\n", encoding="utf-8")
        with pytest.raises(sr.ContractViolationError, match="(?i)director"):
            sr.list_exceptions(str(not_a_dir))

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


class TestListExceptions:
    def test_list_empty(self, sr, tmp_path):
        kb = tmp_path / "kb"
        assert sr.list_exceptions(str(kb)) == []

    def test_list_sorted(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_exception(str(kb), "knowledge/b.md", 2, "crucially", "crucially", reason="other")
        sr.add_exception(str(kb), "knowledge/a.md", 10, "pivotal", "pivotal", reason="other")
        sr.add_exception(str(kb), "knowledge/b.md", 1, "seamless", "seamless", reason="other")
        records = sr.list_exceptions(str(kb))
        assert [(r["key"]["file"], r["key"]["line"]) for r in records] == [
            ("knowledge/a.md", 10),
            ("knowledge/b.md", 1),
            ("knowledge/b.md", 2),
        ]

    def test_load_exception_records_exposes_canonical_tuples(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_exception(str(kb), "knowledge/a.md", 3, "crucially", "crucially", reason="other")
        records = sr.load_exception_records(str(kb))
        assert records[("knowledge/a.md", 3, "crucially", "crucially")]["reason"] == "other"

    def test_list_rejects_invalid_json(self, sr, tmp_path):
        kb = tmp_path / "kb"
        d = _exception_dir(kb)
        d.mkdir(parents=True)
        (d / "bad.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(sr.ContractViolationError):
            sr.list_exceptions(str(kb))

    def test_list_rejects_missing_fields(self, sr, tmp_path):
        kb = tmp_path / "kb"
        d = _exception_dir(kb)
        d.mkdir(parents=True)
        (d / "bad.json").write_text(
            json.dumps({"key": {"file": "a.md", "line": 1, "pattern": "p", "match": "m"}}),
            encoding="utf-8",
        )
        with pytest.raises(sr.ContractViolationError):
            sr.list_exceptions(str(kb))


class TestHandWrittenRecords:
    def test_non_canonical_path_rejected_on_read(self, sr, tmp_path):
        """A hand-written './x.md' key could never match a finding — fail loudly."""
        kb = tmp_path / "kb"
        exception_dir = _exception_dir(kb)
        exception_dir.mkdir(parents=True)
        (exception_dir / "manual.json").write_text(
            json.dumps({
                "schema": "kb-style-exception/v1",
                "key": _key("./knowledge/a.md", 1, "crucially", "crucially"),
                "reason": "other",
                "created": "2026-01-01T00:00:00+00:00",
            }),
            encoding="utf-8",
        )
        with pytest.raises(sr.ContractViolationError, match="(?i)canonical"):
            sr.list_exceptions(str(kb))


class TestRemoveException:
    def test_remove_existing(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_exception(str(kb), "knowledge/a.md", 1, "crucially", "crucially", reason="other")
        assert sr.remove_exception(str(kb), "knowledge/a.md", 1, "crucially", "crucially") is True
        assert list(_exception_dir(kb).glob("*.json")) == []

    def test_remove_missing_returns_false(self, sr, tmp_path):
        kb = tmp_path / "kb"
        assert sr.remove_exception(str(kb), "knowledge/a.md", 1, "crucially", "crucially") is False


class TestAtomicity:
    def test_add_leaves_no_temp_files(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_exception(str(kb), "knowledge/a.md", 1, "crucially", "crucially", reason="other")
        d = _exception_dir(kb)
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
        exception_dir = _exception_dir(kb)
        exception_dir.mkdir(parents=True)
        (exception_dir / "bad.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            sr.main(["list", "--kb", str(kb)])
        assert exc_info.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert "bad.json" in err["error"]


def _legacy_dir(kb_path):
    return kb_path / ".kb" / "style-reviewed"


def _write_legacy(kb_path, name, key, *, reason="subject-matter"):
    legacy = _legacy_dir(kb_path)
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / name).write_text(
        json.dumps(
            {
                "schema": "kb-style-review/v1",
                "key": key,
                "reason": reason,
                "created": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )


class TestLegacyReads:
    """Reads merge both locations and mutate nothing — lint is read-only."""

    def test_read_sees_a_legacy_record(self, sr, tmp_path):
        kb = tmp_path / "kb"
        _write_legacy(kb, "a.json", _key("knowledge/a.md", 3, "pivotal", "pivotal"))

        records = sr.list_exceptions(str(kb))

        assert len(records) == 1
        assert records[0]["key"]["match"] == "pivotal"

    def test_read_does_not_move_anything(self, sr, tmp_path):
        kb = tmp_path / "kb"
        _write_legacy(kb, "a.json", _key("knowledge/a.md", 3, "pivotal", "pivotal"))

        sr.list_exceptions(str(kb))
        sr.load_exception_records(str(kb))

        assert (_legacy_dir(kb) / "a.json").exists()
        assert not _exception_dir(kb).exists()

    def test_read_is_silent_on_success(self, sr, tmp_path, capsys):
        kb = tmp_path / "kb"
        _write_legacy(kb, "a.json", _key("knowledge/a.md", 3, "pivotal", "pivotal"))

        sr.list_exceptions(str(kb))

        assert capsys.readouterr().err == ""

    def test_read_merges_both_directories(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_exception(str(kb), "knowledge/new.md", 1, "crucially", "crucially", reason="other")
        _write_legacy(kb, "a.json", _key("knowledge/old.md", 3, "pivotal", "pivotal"))

        files = {record["key"]["file"] for record in sr.list_exceptions(str(kb))}

        assert files == {"knowledge/new.md", "knowledge/old.md"}

    def test_current_directory_wins_on_the_same_key(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_exception(str(kb), "knowledge/a.md", 3, "pivotal", "pivotal", reason="other")
        _write_legacy(kb, "a.json", _key("knowledge/a.md", 3, "pivotal", "pivotal"))

        records = sr.list_exceptions(str(kb))

        assert len(records) == 1
        assert records[0]["reason"] == "other"

    def test_legacy_records_still_suppress_findings(self, sr, tmp_path):
        kb = tmp_path / "kb"
        _write_legacy(kb, "a.json", _key("knowledge/a.md", 3, "pivotal", "pivotal"))

        loaded = sr.load_exception_records(str(kb))

        assert ("knowledge/a.md", 3, "pivotal", "pivotal") in loaded

    def test_malformed_legacy_record_is_reported_not_ignored(self, sr, tmp_path):
        kb = tmp_path / "kb"
        legacy = _legacy_dir(kb)
        legacy.mkdir(parents=True)
        (legacy / "bad.json").write_text("{not json", encoding="utf-8")

        with pytest.raises(sr.ContractViolationError) as excinfo:
            sr.list_exceptions(str(kb))

        assert "bad.json" in str(excinfo.value)


class TestLegacyMigration:
    """Writes migrate the store across, once — nothing is dropped."""

    def test_add_migrates_legacy_records(self, sr, tmp_path):
        kb = tmp_path / "kb"
        _write_legacy(kb, "a.json", _key("knowledge/a.md", 3, "pivotal", "pivotal"))

        sr.add_exception(str(kb), "knowledge/new.md", 1, "crucially", "crucially", reason="other")

        assert not _legacy_dir(kb).exists()
        migrated = [
            record for record in sr.list_exceptions(str(kb))
            if record["key"]["file"] == "knowledge/a.md"
        ]
        assert len(migrated) == 1
        assert migrated[0]["schema"] == sr.EXCEPTION_SCHEMA
        assert (_exception_dir(kb) / "a.json").exists()

    def test_remove_finds_a_legacy_record(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_exception(str(kb), "knowledge/a.md", 3, "pivotal", "pivotal", reason="other")
        record_name = next(p.name for p in _exception_dir(kb).glob("*.json"))
        (_exception_dir(kb) / record_name).unlink()
        _write_legacy(kb, record_name, _key("knowledge/a.md", 3, "pivotal", "pivotal"))

        removed = sr.remove_exception(str(kb), "knowledge/a.md", 3, "pivotal", "pivotal")

        assert removed is True
        assert sr.list_exceptions(str(kb)) == []

    def test_superseded_legacy_copy_is_not_clobbered(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_exception(str(kb), "knowledge/a.md", 3, "pivotal", "pivotal", reason="other")
        record_name = next(p.name for p in _exception_dir(kb).glob("*.json"))
        _write_legacy(kb, record_name, _key("knowledge/a.md", 3, "pivotal", "pivotal"))

        sr.add_exception(str(kb), "knowledge/b.md", 1, "crucially", "crucially", reason="other")

        assert (_legacy_dir(kb) / record_name).exists()
        records = {r["key"]["file"]: r for r in sr.list_exceptions(str(kb))}
        assert set(records) == {"knowledge/a.md", "knowledge/b.md"}
        assert records["knowledge/a.md"]["reason"] == "other"

    def test_migration_leaves_no_temp_files(self, sr, tmp_path):
        kb = tmp_path / "kb"
        _write_legacy(kb, "a.json", _key("knowledge/a.md", 3, "pivotal", "pivotal"))

        sr.add_exception(str(kb), "knowledge/new.md", 1, "crucially", "crucially", reason="other")

        leftovers = [p.name for p in _exception_dir(kb).iterdir() if p.name.endswith(".tmp")]
        assert leftovers == []

    def test_migration_writes_the_marker(self, sr, tmp_path):
        kb = tmp_path / "kb"
        _write_legacy(kb, "a.json", _key("knowledge/a.md", 3, "pivotal", "pivotal"))

        sr.add_exception(str(kb), "knowledge/new.md", 1, "crucially", "crucially", reason="other")

        assert (_exception_dir(kb) / "README.md").exists()


class TestDirectoryMarker:
    """The directory says what it is, so it does not read as lint scratch."""

    def test_add_writes_a_readme_marker(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_exception(str(kb), "knowledge/a.md", 1, "crucially", "crucially", reason="other")

        marker = _exception_dir(kb) / "README.md"

        assert marker.exists()
        text = marker.read_text(encoding="utf-8").lower()
        assert "exception" in text
        assert "not" in text and "temporary" in text

    def test_marker_is_not_parsed_as_a_record(self, sr, tmp_path):
        kb = tmp_path / "kb"
        sr.add_exception(str(kb), "knowledge/a.md", 1, "crucially", "crucially", reason="other")

        assert len(sr.list_exceptions(str(kb))) == 1
