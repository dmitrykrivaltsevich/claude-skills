"""Helpers for loading kb scripts without polluting global import state."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"


def load_script_module(module_name: str, file_name: str):
    script_path = _SCRIPT_DIR / file_name
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    # Scripts insert their own directory on import, so removing one entry would
    # leave a duplicate behind; snapshot and restore instead.
    saved_path = list(sys.path)
    preexisting_modules = set(sys.modules)
    sys.path.insert(0, str(_SCRIPT_DIR))
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = saved_path
        sys.modules.pop(module_name, None)
        for name, loaded_module in list(sys.modules.items()):
            # Only modules this call imported; a scripts/ module the host owned
            # beforehand is not ours to evict.
            if name in preexisting_modules:
                continue
            file_path = getattr(loaded_module, "__file__", None)
            if not file_path:
                continue
            try:
                resolved = Path(file_path).resolve()
            except OSError:
                continue
            if resolved.parent == _SCRIPT_DIR:
                sys.modules.pop(name, None)

    return module
