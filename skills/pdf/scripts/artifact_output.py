#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Helpers for file-backed JSON output with compact stdout envelopes."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _envelope(payload: Any, output_path: Path, artifact_kind: str) -> dict[str, Any]:
    """Build a compact envelope describing a persisted artifact."""
    envelope: dict[str, Any] = {
        "artifact_path": str(output_path),
        "artifact_kind": artifact_kind,
    }

    if isinstance(payload, list):
        envelope["top_level_type"] = "array"
        envelope["item_count"] = len(payload)
    elif isinstance(payload, dict):
        envelope["top_level_type"] = "object"
        envelope["keys"] = sorted(str(key) for key in payload.keys())
    else:
        envelope["top_level_type"] = type(payload).__name__

    return envelope


def emit_json_result(
    payload: Any,
    *,
    output_path: str | Path | None,
    artifact_kind: str,
) -> None:
    """Emit JSON either directly to stdout or via a file-backed artifact."""
    if output_path is None:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        print(file=sys.stdout)
        return

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    json.dump(_envelope(payload, path, artifact_kind), sys.stdout, ensure_ascii=False, indent=None)
    print(file=sys.stdout)
