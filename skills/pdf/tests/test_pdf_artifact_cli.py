# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pytest >= 8.0",
#   "PyMuPDF >= 1.25",
# ]
# ///
"""CLI tests for PDF artifact mode envelopes."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest


SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Create a small searchable PDF for CLI tests."""
    path = tmp_path / "sample.pdf"
    doc = pymupdf.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "Alpha overview", fontsize=16)
    page1.insert_text((72, 120), "The fox appears on page one.", fontsize=12)
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Beta details", fontsize=16)
    page2.insert_text((72, 120), "The fox appears on page two.", fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


def _run_cli(script_name: str, *args: str) -> dict:
    cmd = [sys.executable, str(SCRIPTS_DIR / script_name), *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(
            f"CLI failed for {script_name}:\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return json.loads(result.stdout)


class TestPdfArtifactCli:
    def test_info_output_writes_artifact_and_returns_envelope(self, sample_pdf: Path, tmp_path: Path):
        output_path = tmp_path / "info.json"

        envelope = _run_cli("info.py", str(sample_pdf), "--output", str(output_path))

        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "pdf-info"
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["page_count"] == 2

    def test_search_output_writes_artifact_and_returns_envelope(self, sample_pdf: Path, tmp_path: Path):
        output_path = tmp_path / "search.json"

        envelope = _run_cli("search.py", str(sample_pdf), "fox", "--output", str(output_path))

        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "pdf-search"
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["query"] == "fox"
        assert payload["total_matches"] >= 2

    def test_read_output_writes_artifact_and_returns_envelope(self, sample_pdf: Path, tmp_path: Path):
        output_path = tmp_path / "read.json"

        envelope = _run_cli(
            "read.py",
            str(sample_pdf),
            "--page-start",
            "1",
            "--page-end",
            "2",
            "--output",
            str(output_path),
        )

        assert envelope["artifact_path"] == str(output_path)
        assert envelope["artifact_kind"] == "pdf-read"
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["pages_returned"] == "1-2"
        assert len(payload["pages"]) == 2
