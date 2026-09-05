"""Tests for style_config.py — style-pattern loading, validation, and merge."""

from __future__ import annotations

import json

import pytest

from ._loader import load_script_module

try:
    _style_config = load_script_module("kb_test_style_config", "style_config.py")
except Exception as exc:  # red phase: module is not implemented yet
    _style_config = None
    _style_config_load_error = exc


DEFAULT_PATTERN_IDS = {
    "load-bearing",
    "not-just-contrast",
    "the-key-insight",
    "paradigm-shift",
    "crucially",
    "deep-dive",
    "tapestry",
    "underscores",
    "delve",
    "testament-to",
    "claude-vocabulary",
    "pivotal",
    "showcases",
    "seamless",
    "realm-of",
    "throat-clearing",
    "claude-ritual",
    "weasel-attribution",
    "filler-frames",
    "hype",
    "litotes",
    "intricate",
    "real-reframe",
    "comparative-kicker",
    "antithesis-pivot",
    "heres-the-thing",
    "the-point-is",
    "directness-signal",
    "upshot-frame",
    "self-answered-question",
    "worth-preamble",
    "weight-metaphor",
}


@pytest.fixture
def sc():
    if _style_config is None:
        pytest.fail(f"style_config.py is not importable: {_style_config_load_error}")
    return _style_config


def _write(path, data) -> "path":
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _kb_root(tmp_path):
    root = tmp_path / "kb"
    (root / ".kb").mkdir(parents=True)
    return root


def _per_kb_file(root):
    return root / ".kb" / "style-patterns.json"


class TestDefaultPatterns:
    def test_default_file_loads_with_expected_patterns(self, sc):
        data = sc.load_pattern_file(sc.DEFAULT_PATTERN_FILE)
        assert data["schema"] == "kb-style-patterns/v1"
        assert len(data["patterns"]) == 32
        assert {p["id"] for p in data["patterns"]} == DEFAULT_PATTERN_IDS

    def test_default_patterns_are_enabled_and_have_notes(self, sc):
        data = sc.load_pattern_file(sc.DEFAULT_PATTERN_FILE)
        for pattern in data["patterns"]:
            assert pattern["enabled"] is True
            assert isinstance(pattern["note"], str)
            assert pattern["note"].strip()

    def test_default_regexes_compile_case_insensitively(self, sc):
        import re

        data = sc.load_pattern_file(sc.DEFAULT_PATTERN_FILE)
        assert "ignorecase" in data["flags"]
        for pattern in data["patterns"]:
            compiled = re.compile(pattern["regex"], re.IGNORECASE)
            assert compiled.pattern


class TestPatternFileValidation:
    def test_rejects_missing_schema(self, sc, tmp_path):
        p = _write(tmp_path / "p.json", {"patterns": [{"id": "a", "regex": "a", "note": "n"}]})
        with pytest.raises(sc.ContractViolationError):
            sc.load_pattern_file(p)

    def test_rejects_wrong_schema(self, sc, tmp_path):
        p = _write(tmp_path / "p.json", {
            "schema": "kb-style-patterns/v2",
            "patterns": [{"id": "a", "regex": "a", "note": "n"}],
        })
        with pytest.raises(sc.ContractViolationError):
            sc.load_pattern_file(p)

    def test_rejects_missing_id(self, sc, tmp_path):
        p = _write(tmp_path / "p.json", {
            "schema": "kb-style-patterns/v1",
            "patterns": [{"regex": "a", "note": "n"}],
        })
        with pytest.raises(sc.ContractViolationError):
            sc.load_pattern_file(p)

    def test_rejects_invalid_regex(self, sc, tmp_path):
        p = _write(tmp_path / "p.json", {
            "schema": "kb-style-patterns/v1",
            "patterns": [{"id": "a", "regex": "(", "note": "n"}],
        })
        with pytest.raises(sc.ContractViolationError):
            sc.load_pattern_file(p)

    def test_rejects_duplicate_ids(self, sc, tmp_path):
        p = _write(tmp_path / "p.json", {
            "schema": "kb-style-patterns/v1",
            "patterns": [
                {"id": "a", "regex": "a", "note": "first"},
                {"id": "a", "regex": "b", "note": "second"},
            ],
        })
        with pytest.raises(sc.ContractViolationError):
            sc.load_pattern_file(p)


class TestFlagSupport:
    def test_multiline_and_dotall_rejected(self, sc, tmp_path):
        """Scanning is per line, so cross-line flags cannot work and must not be advertised."""
        for flag in ("multiline", "dotall"):
            path = tmp_path / f"{flag}.json"
            path.write_text(
                json.dumps({
                    "schema": "kb-style-patterns/v1",
                    "flags": [flag],
                    "patterns": [{"id": "x", "regex": "x", "note": "n"}],
                }),
                encoding="utf-8",
            )
            with pytest.raises(sc.ContractViolationError, match="(?i)ignorecase"):
                sc.load_pattern_file(path)


class TestUnreadablePatternFile:
    def test_non_utf8_pattern_file_rejected(self, sc, tmp_path):
        """UnicodeDecodeError is a ValueError, so an OSError-only catch lets it escape."""
        path = tmp_path / "bad-encoding.json"
        path.write_bytes(b'{"schema": "kb-style-patterns/v1", "patterns": [], "n": "\xff\xfe"}')
        with pytest.raises(sc.ContractViolationError, match="(?i)could not read"):
            sc.load_pattern_file(path)


class TestEffectivePatternMerge:
    def test_default_is_used_when_no_overrides(self, sc, tmp_path):
        root = _kb_root(tmp_path)
        entries = sc.effective_pattern_entries(kb_path=str(root))
        by_id = {entry.id: entry for entry in entries}
        assert set(by_id) == DEFAULT_PATTERN_IDS
        assert by_id["pivotal"].source == "default"
        assert all(entry.enabled for entry in entries)

    def test_per_kb_adds_and_overrides(self, sc, tmp_path):
        root = _kb_root(tmp_path)
        _write(
            _per_kb_file(root),
            {
                "schema": "kb-style-patterns/v1",
                "patterns": [
                    {"id": "pivotal", "enabled": True, "regex": r"\bpivotal\b", "note": "per-kb"},
                    {"id": "custom", "enabled": True, "regex": r"\bcustom\b", "note": "new"},
                ],
            },
        )
        entries = sc.effective_pattern_entries(kb_path=str(root))
        by_id = {entry.id: entry for entry in entries}
        assert by_id["pivotal"].source == "per-kb"
        assert by_id["pivotal"].note == "per-kb"
        assert by_id["custom"].source == "per-kb"
        assert by_id["load-bearing"].source == "default"

    def test_cli_beats_per_kb(self, sc, tmp_path):
        root = _kb_root(tmp_path)
        _write(
            _per_kb_file(root),
            {
                "schema": "kb-style-patterns/v1",
                "patterns": [
                    {"id": "pivotal", "enabled": True, "regex": r"\bpivotal\b", "note": "per-kb"},
                    {"id": "custom", "enabled": True, "regex": r"\bcustom\b", "note": "per-kb new"},
                ],
            },
        )
        cli = _write(
            tmp_path / "cli.json",
            {
                "schema": "kb-style-patterns/v1",
                "patterns": [
                    {"id": "pivotal", "enabled": True, "regex": r"\bpivotal\b", "note": "cli"},
                ],
            },
        )
        entries = sc.effective_pattern_entries(kb_path=str(root), cli_patterns=str(cli))
        by_id = {entry.id: entry for entry in entries}
        assert by_id["pivotal"].source == "cli"
        assert by_id["pivotal"].note == "cli"
        assert by_id["custom"].source == "per-kb"
        assert by_id["custom"].note == "per-kb new"

    def test_disabled_pattern_is_excluded_from_active(self, sc, tmp_path):
        root = _kb_root(tmp_path)
        _write(
            _per_kb_file(root),
            {
                "schema": "kb-style-patterns/v1",
                "patterns": [
                    {"id": "pivotal", "enabled": False, "regex": r"\bpivotal\b", "note": "off"},
                    {"id": "custom", "enabled": False, "regex": r"\bcustom\b", "note": "off"},
                ],
            },
        )
        entries = sc.effective_pattern_entries(kb_path=str(root))
        active = sc.effective_patterns(kb_path=str(root))
        active_ids = {entry.id for entry in active}
        by_id = {entry.id: entry for entry in entries}
        assert by_id["pivotal"].enabled is False
        assert "pivotal" not in active_ids
        assert "custom" not in active_ids
        disabled = sc.disabled_pattern_ids(entries)
        assert "pivotal" in disabled
        assert "custom" in disabled

    def test_invalid_cli_file_fails_loudly(self, sc, tmp_path):
        root = _kb_root(tmp_path)
        bad = _write(
            tmp_path / "bad.json",
            {"schema": "kb-style-patterns/v2", "patterns": []},
        )
        with pytest.raises(sc.ContractViolationError):
            sc.effective_pattern_entries(kb_path=str(root), cli_patterns=str(bad))