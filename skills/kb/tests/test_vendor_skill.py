"""Tests for vendor_skill.py — portable vendored kb skill (init vendors the
skill into the KB so any harness works with zero install)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ._loader import load_script_module

vendor_skill = load_script_module("kb_test_vendor_skill", "vendor_skill.py")
init = load_script_module("kb_test_vendor_init", "init.py")
open_mod = load_script_module("kb_test_vendor_open", "open.py")
lint = load_script_module("kb_test_vendor_lint", "lint.py")
ContractViolationError = vendor_skill.ContractViolationError


def _scaffold(path: Path, vendor: bool = True) -> None:
    init.scaffold_kb(str(path), "Vendor KB", vendor_skill=vendor)


class TestVersionPin:
    def test_skill_version_matches_marketplace(self):
        # marketplace.json lives outside the skill and is unreachable from
        # installed layouts, so the skill carries its own version — pinned
        # here so a bump can never update one without the other.
        root = Path(__file__).resolve().parent.parent.parent.parent
        marketplace = json.loads(
            (root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        assert vendor_skill.SKILL_VERSION == marketplace["metadata"]["version"]


class TestVendorPayload:
    def test_runtime_only_payload(self, tmp_path: Path):
        kb = tmp_path / "kb"
        _scaffold(kb, vendor=False)
        vendor_skill.vendor(str(kb))
        canonical = kb / ".agents" / "skills" / "kb"
        assert (canonical / "SKILL.md").is_file()
        assert (canonical / "scripts" / "init.py").is_file()
        assert (canonical / "scripts" / "lint.py").is_file()
        assert (canonical / "references" / "parallel-import.md").is_file()
        assert not (canonical / "tests").exists()  # 2.5MB of fixtures stay out
        assert not (canonical / "README.md").exists()

    def test_stamp_records_version(self, tmp_path: Path):
        kb = tmp_path / "kb"
        _scaffold(kb, vendor=False)
        vendor_skill.vendor(str(kb))
        stamp = json.loads(
            (kb / ".agents" / "skills" / "kb" / ".vendor.json").read_text(
                encoding="utf-8"
            )
        )
        assert stamp["skill"] == "kb"
        assert stamp["version"] == vendor_skill.SKILL_VERSION
        assert sorted(stamp["payload"]) == ["SKILL.md", "references", "scripts"]

    def test_fixed_point_replay(self, tmp_path: Path):
        kb = tmp_path / "kb"
        _scaffold(kb, vendor=False)
        vendor_skill.vendor(str(kb))

        def snapshot() -> dict[str, bytes]:
            out = {}
            for p in sorted((kb / ".agents").rglob("*")):
                if p.is_file() and not p.is_symlink():
                    out[p.relative_to(kb).as_posix()] = p.read_bytes()
            # Aliases are symlinks: record the link target, not the tree
            # behind it (walking into the link would re-snapshot canonical).
            for _name, rel in vendor_skill.ALIASES.items():
                out[rel.as_posix()] = os.readlink(kb / rel).encode()
            agent = kb / ".github" / "agents" / "kb.agent.md"
            out[".github/agents/kb.agent.md"] = agent.read_bytes()
            return out

        before = snapshot()
        vendor_skill.vendor(str(kb))
        assert snapshot() == before  # replay changes zero bytes


class TestAliases:
    def test_claude_symlink_relative_and_confined(self, tmp_path: Path):
        kb = tmp_path / "kb"
        _scaffold(kb, vendor=False)
        vendor_skill.vendor(str(kb))
        link = kb / ".claude" / "skills" / "kb"
        assert link.is_symlink()
        target = os.readlink(link)
        assert not os.path.isabs(target)  # git preserves relative links on clone
        assert (link / "SKILL.md").is_file()  # resolves to the canonical copy
        assert (link.resolve()).is_relative_to(kb.resolve())  # no escapes

    def test_table_matches_filesystem(self, tmp_path: Path):
        kb = tmp_path / "kb"
        _scaffold(kb, vendor=False)
        vendor_skill.vendor(str(kb))
        for _name, rel in vendor_skill.ALIASES.items():
            assert (kb / rel).is_symlink(), f"alias {rel} missing"

    def test_unlink_and_readd_roundtrip(self, tmp_path: Path):
        kb = tmp_path / "kb"
        _scaffold(kb, vendor=False)
        vendor_skill.vendor(str(kb))
        vendor_skill.unlink_aliases(str(kb))
        assert not (kb / ".claude" / "skills" / "kb").exists()
        # Canonical copy and agent file survive unlink (aliases only).
        assert (kb / ".agents" / "skills" / "kb" / "SKILL.md").is_file()
        assert (kb / ".github" / "agents" / "kb.agent.md").is_file()
        vendor_skill.add_alias(str(kb), "claude")
        assert (kb / ".claude" / "skills" / "kb").is_symlink()

    def test_add_alias_unknown_name(self, tmp_path: Path):
        kb = tmp_path / "kb"
        _scaffold(kb, vendor=False)
        vendor_skill.vendor(str(kb))
        with pytest.raises(ContractViolationError):
            vendor_skill.add_alias(str(kb), "no-such-harness")


class TestAgentFile:
    def test_pointer_not_fork(self, tmp_path: Path):
        kb = tmp_path / "kb"
        _scaffold(kb, vendor=False)
        vendor_skill.vendor(str(kb))
        agent = kb / ".github" / "agents" / "kb.agent.md"
        text = agent.read_text(encoding="utf-8")
        assert ".agents/skills/kb/SKILL.md" in text  # points at the skill
        assert text.startswith("---")  # Copilot custom-agent frontmatter
        assert "name:" in text.split("---")[1]
        assert "description:" in text.split("---")[1]
        # A pointer file, not a forked workflow: small enough to stay a stub.
        assert len(text.splitlines()) <= 40


class TestCheckAndRefresh:
    def test_check_fresh(self, tmp_path: Path):
        kb = tmp_path / "kb"
        _scaffold(kb, vendor=False)
        vendor_skill.vendor(str(kb))
        report = vendor_skill.check(str(kb))
        assert report["stale"] is False
        assert report["vendored_version"] == vendor_skill.SKILL_VERSION

    def test_check_missing_stamp_is_stale(self, tmp_path: Path):
        kb = tmp_path / "kb"
        _scaffold(kb, vendor=False)
        report = vendor_skill.check(str(kb))
        assert report["stale"] is True
        assert "refresh" in report["detail"].lower()

    def test_check_stale_after_upgrade(self, tmp_path: Path, monkeypatch):
        kb = tmp_path / "kb"
        _scaffold(kb, vendor=False)
        vendor_skill.vendor(str(kb))
        monkeypatch.setattr(vendor_skill, "SKILL_VERSION", "0.0.0-test")
        report = vendor_skill.check(str(kb))
        assert report["stale"] is True
        assert "refresh" in report["detail"].lower()

    def test_refresh_converges(self, tmp_path: Path, monkeypatch):
        kb = tmp_path / "kb"
        _scaffold(kb, vendor=False)
        vendor_skill.vendor(str(kb))
        monkeypatch.setattr(vendor_skill, "SKILL_VERSION", "0.0.0-test")
        vendor_skill.refresh(str(kb))
        assert vendor_skill.check(str(kb))["stale"] is False

    def test_self_vendor_refused(self, tmp_path: Path, monkeypatch):
        # Refreshing from the vendored copy would stamp the OLD version as
        # current — a silent lie. The running script must never be inside
        # the target KB's vendored tree.
        kb = tmp_path / "kb"
        _scaffold(kb, vendor=False)
        fake_root = kb / ".agents" / "skills" / "kb"
        (fake_root / "scripts").mkdir(parents=True)
        monkeypatch.setattr(vendor_skill, "_SKILL_ROOT", fake_root)
        with pytest.raises(ContractViolationError):
            vendor_skill.vendor(str(kb))


class TestInitFlags:
    def test_default_init_vendors(self, tmp_path: Path):
        kb = tmp_path / "kb"
        _scaffold(kb)
        assert (kb / ".agents" / "skills" / "kb" / "SKILL.md").is_file()
        assert (kb / ".claude" / "skills" / "kb").is_symlink()
        assert (kb / ".github" / "agents" / "kb.agent.md").is_file()

    def test_no_skill_opts_out(self, tmp_path: Path):
        kb = tmp_path / "kb"
        _scaffold(kb, vendor=False)
        assert not (kb / ".agents").exists()
        assert not (kb / ".claude").exists()
        assert not (kb / ".github").exists()

    def test_no_aliases_keeps_canonical(self, tmp_path: Path):
        kb = tmp_path / "kb"
        init.scaffold_kb(str(kb), "Vendor KB", vendor_skill=True, aliases=False)
        assert (kb / ".agents" / "skills" / "kb" / "SKILL.md").is_file()
        assert not (kb / ".claude").exists()


class TestScanHygiene:
    def test_harness_dirs_excluded_from_style_scan(self):
        excluded = lint._STYLE_EXCLUDED_DIRS
        assert (".agents",) in excluded
        assert (".claude",) in excluded
        assert (".github",) in excluded

    def test_vendored_kb_lints_clean(self, tmp_path: Path):
        kb = tmp_path / "kb"
        _scaffold(kb)
        result = lint.lint_kb(str(kb))
        flagged = [
            f.get("file", "")
            for f in result.get("issues", [])
            if f.get("file", "").split("/")[0] in (".agents", ".claude", ".github")
        ]
        assert flagged == []

    def test_open_stats_ignore_harness_dirs(self, tmp_path: Path):
        kb = tmp_path / "kb"
        _scaffold(kb, vendor=False)
        plain = open_mod.open_kb(str(kb), stats=True)
        _scaffold(tmp_path / "kb2")
        vendored = open_mod.open_kb(str(tmp_path / "kb2"), stats=True)
        assert vendored["total_files"] == plain["total_files"]
        assert vendored["total_links"] == plain["total_links"]


class TestOpenVendorStatus:
    def test_unvendored_kb(self, tmp_path: Path):
        kb = tmp_path / "kb"
        _scaffold(kb, vendor=False)
        status = open_mod.open_kb(str(kb))["skill_vendor"]
        assert status == {"vendored": False, "version": None, "stale": False}

    def test_vendored_kb(self, tmp_path: Path):
        kb = tmp_path / "kb"
        _scaffold(kb)
        status = open_mod.open_kb(str(kb))["skill_vendor"]
        assert status["vendored"] is True
        assert status["version"] == vendor_skill.SKILL_VERSION
        assert status["stale"] is False

    def test_stale_surfaces_on_open(self, tmp_path: Path, monkeypatch):
        kb = tmp_path / "kb"
        _scaffold(kb)
        # open.py imports vendor_skill as its own module instance (loader
        # isolation), so the upgrade is simulated on the instance open reads.
        monkeypatch.setattr(open_mod.vendor_skill, "SKILL_VERSION", "0.0.0-test")
        status = open_mod.open_kb(str(kb))["skill_vendor"]
        assert status["stale"] is True
