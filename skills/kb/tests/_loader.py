"""Helpers for loading kb scripts without polluting global import state."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"


def load_script_module(module_name: str, file_name: str):
    script_path = _SCRIPT_DIR / file_name
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None

    sys.path.insert(0, str(_SCRIPT_DIR))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(_SCRIPT_DIR))
        for name, loaded_module in list(sys.modules.items()):
            file_path = getattr(loaded_module, "__file__", None)
            if not file_path:
                continue
            try:
                resolved = Path(file_path).resolve()
            except OSError:
                continue
            if resolved.parent == _SCRIPT_DIR and name != module_name:
                sys.modules.pop(name, None)

    return module