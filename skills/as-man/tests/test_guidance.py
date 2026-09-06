"""Guardrail tests — the prose contracts this skill depends on must stay in place.

The scripts cannot enforce composition rules; SKILL.md and the references do.
These tests fail if a rewrite silently drops one of them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL_MD = SKILL_DIR / "SKILL.md"
REFERENCES = SKILL_DIR / "references"

# AGENTS.md caps SKILL.md bodies so the context window stays a shared resource.
MAX_SKILL_LINES = 500
MAX_NAME_CHARS = 64
MAX_DESCRIPTION_CHARS = 1024

# AGENTS.md: reference files over this length should open with a table of contents.
TOC_REQUIRED_OVER = 100

GENRE_FILES = (
    "research-paper",
    "technical-book",
    "system-paper",
    "postmortem",
    "design-doc",
    "standard-spec",
    "periodical",
    "popular-science",
    "policy-position",
    "tool-doc",
    "news-article",
)

MD_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _skill_text() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


def _frontmatter() -> dict[str, str]:
    text = _skill_text()
    _, block, _ = text.split("---", 2)
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if re.match(r"^[a-z-]+:", line):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


class TestFrontmatter:
    def test_name_matches_the_directory(self):
        assert _frontmatter()["name"] == SKILL_DIR.name

    def test_name_is_kebab_case_without_a_leading_slash(self):
        name = _frontmatter()["name"]

        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name)
        assert len(name) <= MAX_NAME_CHARS

    def test_description_states_when_to_use_the_skill(self):
        description = _frontmatter()["description"]

        assert "Use when" in description
        assert len(description) <= MAX_DESCRIPTION_CHARS

    def test_description_omits_implementation_detail(self):
        description = _frontmatter()["description"].lower()

        for leak in ("uv run", "pep 723", "keychain", "json", "script"):
            assert leak not in description

    def test_skill_is_user_invocable(self):
        assert _frontmatter()["user-invocable"] == "true"


class TestSkillBody:
    def test_body_stays_under_the_line_cap(self):
        assert len(_skill_text().splitlines()) <= MAX_SKILL_LINES

    def test_the_outline_contract_is_stated_as_mandatory(self):
        text = _skill_text()

        assert "MANDATORY — the outline is a contract" in text
        assert "Never invent a node outside the committed outline" in text

    def test_the_integrity_rule_is_stated_as_mandatory(self):
        text = _skill_text()

        assert "MANDATORY — integrity" in text
        assert "never silently add a fact the source does not contain" in text

    def test_sibling_skills_are_reused_rather_than_reimplemented(self):
        text = _skill_text()

        assert "Never reimplement a sibling skill's job here." in text
        for sibling in ("duckduckgo", "pdf", "deep-research", "kb"):
            assert sibling in text

    def test_only_one_genre_file_may_be_loaded(self):
        text = _skill_text()

        assert "exactly one" in text.lower()
        assert "Do not load more than one genre file" in text

    def test_lazy_realisation_is_required(self):
        text = _skill_text()

        assert "Do not write the whole page up front." in text
        assert "Do not regenerate a realised section." in text

    def test_the_language_contract_is_required_before_composing(self):
        assert "references/language.md" in _skill_text()

    def test_scripts_are_invoked_with_no_config(self):
        text = _skill_text()

        for line in text.splitlines():
            if "scripts/" in line and "uv run" in line:
                assert "--no-config" in line

    def test_no_backslash_paths(self):
        assert "\\scripts" not in _skill_text()


class TestReferencesResolve:
    def _skill_links(self) -> list[str]:
        return [
            target
            for target in MD_LINK.findall(_skill_text())
            if target.endswith(".md")
        ]

    def test_every_link_in_skill_md_exists(self):
        for target in self._skill_links():
            assert (SKILL_DIR / target).is_file(), target

    def test_every_reference_file_is_linked_from_skill_md(self):
        linked = {(SKILL_DIR / target).resolve() for target in self._skill_links()}

        for path in REFERENCES.rglob("*.md"):
            assert path.resolve() in linked, f"{path} is not linked from SKILL.md"

    def test_every_genre_file_is_present_and_linked(self):
        for genre in GENRE_FILES:
            path = REFERENCES / "gaps" / f"{genre}.md"
            assert path.is_file(), genre
            assert f"references/gaps/{genre}.md" in _skill_text()

    def test_references_are_never_chained(self):
        """AGENTS.md forbids SKILL.md -> A.md -> B.md; a reference may not link a reference."""
        for path in REFERENCES.rglob("*.md"):
            for target in MD_LINK.findall(path.read_text(encoding="utf-8")):
                assert not target.endswith(".md"), f"{path} links to {target}"

    def test_long_references_open_with_a_table_of_contents(self):
        for path in REFERENCES.rglob("*.md"):
            lines = path.read_text(encoding="utf-8").splitlines()
            if len(lines) > TOC_REQUIRED_OVER:
                assert "## Contents" in "\n".join(lines[:20]), path


class TestReferenceContent:
    def test_gap_analysis_routes_every_genre(self):
        text = (REFERENCES / "gap-analysis.md").read_text(encoding="utf-8")

        for genre in GENRE_FILES:
            assert f"gaps/{genre}.md" in text

    def test_gap_analysis_states_the_materiality_test(self):
        text = (REFERENCES / "gap-analysis.md").read_text(encoding="utf-8")

        assert "materially worse decision" in text
        assert "Out of scope is not a gap" in text

    def test_gap_analysis_fixes_the_unverified_stamp(self):
        text = (REFERENCES / "gap-analysis.md").read_text(encoding="utf-8")

        assert "[unverified - model knowledge, confirm before acting]" in text

    def test_every_genre_file_carries_expected_coverage_and_traps(self):
        for genre in GENRE_FILES:
            text = (REFERENCES / "gaps" / f"{genre}.md").read_text(encoding="utf-8")

            assert "## Expected coverage" in text, genre
            assert "## Genre traps" in text, genre

    def test_language_contract_bans_the_constructions_it_must_ban(self):
        text = (REFERENCES / "language.md").read_text(encoding="utf-8")

        for rule in ("Idiom", "Phrasal verbs", "Hedges", "Contractions", "ISO 8601"):
            assert rule in text

    def test_language_contract_handles_non_english_sources(self):
        text = (REFERENCES / "language.md").read_text(encoding="utf-8")

        assert "Source language" in text

    def test_understanding_test_defines_every_question_type(self):
        text = (REFERENCES / "understanding-test.md").read_text(encoding="utf-8")

        for kind in ("recall", "application", "discrimination", "consequence", "transfer", "trap"):
            assert f"`{kind}`" in text

    def test_understanding_test_keeps_grading_with_the_model(self):
        text = (REFERENCES / "understanding-test.md").read_text(encoding="utf-8")

        assert "You grade. The script only stores the verdict and counts it." in text

    def test_man_format_lists_the_navigation_keys(self):
        text = (REFERENCES / "man-format.md").read_text(encoding="utf-8")

        for key in ("n  next", "$  last section", "g  what is missing", "t  test my understanding"):
            assert key in text

    def test_no_key_collides_with_a_harness_input_prefix(self):
        """`!` `/` `#` `@` are intercepted by the harness and never reach the skill."""
        text = (REFERENCES / "man-format.md").read_text(encoding="utf-8")
        key_block = text.split("Show these only when the reader presses")[1].split("```")[1]

        for line in key_block.splitlines():
            for token in (tok.strip() for tok in line.split("  ")):
                if token and token[0] in "!/#@":
                    raise AssertionError(f"key {token!r} starts with a reserved prefix")

    def test_the_reserved_prefixes_are_explained_so_they_are_not_reintroduced(self):
        text = (REFERENCES / "man-format.md").read_text(encoding="utf-8")

        assert "reserves for its own input" in text
        assert "Never reassign a key to" in text

    def test_skill_routing_uses_the_same_keys_as_the_reference(self):
        skill = _skill_text()

        assert 't or "test my understanding"' in skill
        assert 'g or "what is not in this doc"' in skill
        assert "n p c u $ s" in skill

    def test_man_format_defines_every_detail_level(self):
        text = (REFERENCES / "man-format.md").read_text(encoding="utf-8")

        assert "## Detail levels" in text
        for level in ("`terse`", "`full`", "`tutorial`"):
            assert level in text

    def test_raising_detail_may_not_loosen_the_register(self):
        text = (REFERENCES / "man-format.md").read_text(encoding="utf-8")

        assert "More detail means more sentences, not longer ones." in text
        assert "The register never changes between levels." in text

    def test_the_detail_keys_are_documented(self):
        text = (REFERENCES / "man-format.md").read_text(encoding="utf-8")

        assert "v  more detail" in text
        assert "b  briefer" in text

    def test_man_format_documents_tagged_paragraphs(self):
        text = (REFERENCES / "man-format.md").read_text(encoding="utf-8")

        assert "tagged paragraph" in text
        assert "at least two spaces after each colon" in text

    def test_gap_template_uses_the_tagged_form(self):
        text = (REFERENCES / "gap-analysis.md").read_text(encoding="utf-8")

        for label in ("Kind:", "Materiality:", "Missing:", "Effect:", "Evidence:"):
            assert f"\n{label}" in text

    def test_man_format_documents_jumping_to_a_numbered_entry(self):
        text = (REFERENCES / "man-format.md").read_text(encoding="utf-8")

        assert "12 go to entry 12" in text
        assert "A bare number is a jump" in text


class TestScriptsMatchTheDocumentation:
    def _script(self, name: str) -> str:
        return (SKILL_DIR / "scripts" / name).read_text(encoding="utf-8")

    def test_every_documented_state_command_exists(self):
        source = self._script("state.py")

        for command in (
            "describe", "add-nodes", "outline", "enter", "realise", "detail", "trail",
            "quiz-add", "quiz-next", "quiz-record", "quiz-report",
            "gaps-add", "gaps-list", "status",
        ):
            assert f'"{command}"' in source, command

    def test_there_is_no_init_command(self):
        assert '"init"' not in self._script("state.py")

    def test_enter_accepts_a_position_as_well_as_an_id(self):
        source = self._script("state.py")

        assert '"--position"' in source
        assert '"--under"' in source
        assert "--position N --under ID" in _skill_text()

    def test_scripts_declare_pep_723_metadata(self):
        for name in ("state.py", "render.py", "contracts.py"):
            assert self._script(name).splitlines()[0:4][-1] == "# ///" or "# /// script" in self._script(name)

    @pytest.mark.parametrize("name", ["state.py", "render.py"])
    def test_scripts_have_no_third_party_dependencies(self, name: str):
        source = self._script(name)
        block = source.split("# ///")[1]

        assert "dependencies = []" in block
