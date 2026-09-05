"""Tests for the test-suite script loader itself."""

from __future__ import annotations

import sys

from ._loader import load_script_module


class TestLoaderIsolation:
    def test_sys_path_is_restored_exactly(self):
        """Scripts insert their own dir on import; the loader must undo all of it."""
        before = list(sys.path)
        load_script_module("kb_test_loader_probe", "lint.py")
        assert sys.path == before

    def test_repeated_loads_do_not_accumulate(self):
        before = list(sys.path)
        for index in range(3):
            load_script_module(f"kb_test_loader_probe_{index}", "style_config.py")
        assert sys.path == before

    def test_loaded_module_is_not_left_in_sys_modules(self):
        load_script_module("kb_test_loader_probe_once", "style_review.py")
        assert "kb_test_loader_probe_once" not in sys.modules

    def test_preexisting_scripts_modules_are_not_evicted(self):
        """Only modules this call created may be cleaned up."""
        import importlib.util
        from pathlib import Path

        script_dir = Path(__file__).resolve().parent.parent / "scripts"
        spec = importlib.util.spec_from_file_location(
            "kb_host_owned_contracts", script_dir / "contracts.py"
        )
        host_module = importlib.util.module_from_spec(spec)
        sys.modules["kb_host_owned_contracts"] = host_module
        spec.loader.exec_module(host_module)
        try:
            load_script_module("kb_test_loader_probe_evict", "lint.py")
            assert "kb_host_owned_contracts" in sys.modules
        finally:
            sys.modules.pop("kb_host_owned_contracts", None)
