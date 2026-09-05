"""Tests for render.py — deterministic 80-column manual-page typesetting."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load(module_name: str, file_name: str):
    script_path = Path(__file__).resolve().parent.parent / "scripts" / file_name
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


render = _load("as_man_render", "render.py")

# Taken from the module under test so the class object is identical.
ContractViolationError = render.ContractViolationError


PAGE = """## NAME

datalog - a declarative query language

## DESCRIPTION

A rule has a head and a body. The body is a list of goals. Evaluation repeats
until no new facts appear. This is called a fixed point.

### Recursion

A rule may refer to itself. Termination is guaranteed when the data is finite.

```
path(X, Y) :- edge(X, Y).
path(X, Y) :- edge(X, Z), path(Z, Y).
```

## SEE ALSO

prolog(7), sql(7)
"""


@pytest.fixture()
def page(tmp_path: Path) -> Path:
    target = tmp_path / "page.md"
    target.write_text(PAGE, encoding="utf-8")
    return target


class TestSectionLayout:
    def test_heading_is_uppercase_and_flush_left(self, page: Path):
        out = render.render_section(page, heading="DESCRIPTION")

        assert out.splitlines()[0] == "DESCRIPTION"

    def test_heading_lookup_is_case_insensitive(self, page: Path):
        assert render.render_section(page, heading="description").startswith("DESCRIPTION")

    def test_body_is_indented_seven_spaces(self, page: Path):
        body = [ln for ln in render.render_section(page, heading="NAME").splitlines() if ln.strip()][1]

        assert body.startswith(" " * 7)
        assert body.strip() == "datalog - a declarative query language"

    def test_prose_never_exceeds_the_width(self, page: Path):
        out = render.render_section(page, heading="SEE ALSO", width=60)

        assert max(len(line) for line in out.splitlines()) <= 60

    def test_prose_wraps_even_at_a_narrow_width(self, page: Path):
        out = render.render_section(page, heading="NAME", width=30)

        assert max(len(line) for line in out.splitlines()) <= 30

    def test_code_may_overflow_because_rewrapping_would_change_its_meaning(self, page: Path):
        out = render.render_section(page, heading="DESCRIPTION", width=40)
        prose = [
            line for line in out.splitlines()
            if line.strip() and ":-" not in line and not line.strip().startswith("path(")
        ]

        assert max(len(line) for line in prose) <= 40
        assert "path(X, Y) :- edge(X, Z), path(Z, Y)." in out

    def test_subsection_heading_is_indented_three(self, page: Path):
        line = next(
            ln for ln in render.render_section(page, heading="DESCRIPTION").splitlines()
            if ln.strip() == "Recursion"
        )

        assert line == " " * 3 + "Recursion"

    def test_code_block_is_not_rewrapped(self, page: Path):
        out = render.render_section(page, heading="DESCRIPTION", width=40)

        assert "path(X, Y) :- edge(X, Z), path(Z, Y)." in out

    def test_code_block_fences_are_not_printed(self, page: Path):
        assert "```" not in render.render_section(page, heading="DESCRIPTION")

    def test_paragraphs_stay_separated(self, page: Path):
        assert "\n\n" in render.render_section(page, heading="DESCRIPTION")

    def test_unknown_heading_is_rejected(self, page: Path):
        with pytest.raises(ContractViolationError):
            render.render_section(page, heading="BUGS")

    def test_missing_file_is_rejected(self, tmp_path: Path):
        with pytest.raises(ContractViolationError):
            render.render_section(tmp_path / "nope.md", heading="NAME")

    def test_width_must_be_sensible(self, page: Path):
        with pytest.raises(ContractViolationError):
            render.render_section(page, heading="NAME", width=5)


class TestPromptLine:
    def test_prompt_carries_name_position_and_section(self):
        line = render.prompt_line(name="datalog(7)", position="12/27", section="RECURSIVE QUERIES")

        assert "datalog(7)" in line
        assert "12/27" in line
        assert "RECURSIVE QUERIES" in line

    def test_prompt_hints_at_the_key_list(self):
        assert "(h for keys)" in render.prompt_line(name="datalog(7)", position="1/7", section="NAME")

    def test_prompt_at_the_end_offers_gaps_instead(self):
        line = render.prompt_line(name="datalog(7)", position="7/7", section="SEE ALSO", end=True)

        assert "END" in line
        assert "!" in line
        assert "(h for keys)" not in line

    def test_prompt_is_a_single_line(self):
        line = render.prompt_line(name="datalog(7)", position="1/7", section="NAME")

        assert "\n" not in line

    def test_prompt_never_exceeds_the_width(self):
        line = render.prompt_line(
            name="a-very-long-manual-page-name(7)",
            position="128/256",
            section="A SECTION WITH A NOTABLY LONG HEADING INDEED",
            width=80,
        )

        assert len(line) <= 80

    def test_prompt_right_aligns_the_hint(self):
        line = render.prompt_line(name="datalog(7)", position="1/7", section="NAME", width=80)

        assert line.endswith("(h for keys)")


class TestContents:
    def _outline(self) -> dict:
        return {
            "parent": {"id": "root", "heading": "root", "level": 0, "status": "enumerated"},
            "children": [
                {
                    "id": "name", "heading": "NAME", "promise": "What datalog is.",
                    "status": "realised", "level": 1, "position": 1, "sibling_count": 3,
                    "line_start": 1, "line_end": 3,
                },
                {
                    "id": "desc", "heading": "DESCRIPTION", "promise": "How evaluation works.",
                    "status": "planned", "level": 1, "position": 2, "sibling_count": 3,
                    "line_start": None, "line_end": None,
                },
                {
                    "id": "see", "heading": "SEE ALSO", "promise": "Neighbouring languages.",
                    "status": "planned", "level": 1, "position": 3, "sibling_count": 3,
                    "line_start": None, "line_end": None,
                },
            ],
        }

    def test_contents_lists_every_child_with_its_position(self):
        out = render.render_contents(self._outline())

        assert "1" in out and "NAME" in out
        assert "3" in out and "SEE ALSO" in out

    def test_contents_shows_the_promise(self):
        assert "How evaluation works." in render.render_contents(self._outline())

    def test_contents_marks_what_has_been_read(self):
        out = render.render_contents(self._outline())
        name_line = next(ln for ln in out.splitlines() if "NAME" in ln)
        desc_line = next(ln for ln in out.splitlines() if "DESCRIPTION" in ln)

        assert name_line != desc_line
        assert "*" in name_line
        assert "*" not in desc_line

    def test_contents_respects_the_width(self):
        out = render.render_contents(self._outline(), width=50)

        assert max(len(line) for line in out.splitlines()) <= 50

    def test_contents_needs_a_children_key(self):
        with pytest.raises(ContractViolationError):
            render.render_contents({"parent": {}})


class TestCli:
    def _run(self, tmp_path: Path, page: Path, *args: str) -> str:
        import subprocess
        import sys as _sys

        script = Path(__file__).resolve().parent.parent / "scripts" / "render.py"
        result = subprocess.run(
            [_sys.executable, str(script), *args],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout

    def test_cli_renders_a_section_as_plain_text(self, tmp_path: Path, page: Path):
        out = self._run(tmp_path, page, "--file", str(page), "--section", "NAME")

        assert out.startswith("NAME")
        assert not out.lstrip().startswith("{")

    def test_cli_appends_the_prompt_when_a_name_is_given(self, tmp_path: Path, page: Path):
        out = self._run(
            tmp_path, page, "--file", str(page), "--section", "NAME",
            "--name", "datalog(7)", "--position", "1/3",
        )

        assert out.rstrip().endswith("(h for keys)")

    def test_cli_renders_contents_from_an_outline_file(self, tmp_path: Path, page: Path):
        outline_file = tmp_path / "outline.json"
        outline_file.write_text(json.dumps(TestContents()._outline()), encoding="utf-8")

        out = self._run(tmp_path, page, "--toc-file", str(outline_file))

        assert "NAME" in out and "SEE ALSO" in out

    def test_cli_reports_an_unknown_section_on_stderr(self, page: Path):
        import subprocess
        import sys as _sys

        script = Path(__file__).resolve().parent.parent / "scripts" / "render.py"
        result = subprocess.run(
            [_sys.executable, str(script), "--file", str(page), "--section", "BUGS"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "BUGS" in result.stderr
