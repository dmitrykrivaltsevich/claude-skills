"""Tests for state.py — outline tree, navigation, quiz, and gaps."""

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


state = _load("as_man_state", "state.py")

# Take the exception class from the module under test: state.py imports contracts
# through sys.path, so a separately loaded copy would be a different class object.
ContractViolationError = state.ContractViolationError


def _nodes(*headings: str) -> list[dict]:
    return [{"heading": h, "promise": f"About {h}."} for h in headings]


@pytest.fixture()
def sdir(tmp_path: Path) -> Path:
    return tmp_path / "session"


class TestSessionCreation:
    def test_first_write_creates_session_without_init(self, sdir: Path):
        result = state.add_nodes(sdir, parent="root", nodes=_nodes("NAME", "DESCRIPTION"))

        assert (sdir / "session.json").is_file()
        assert result["parent"] == "root"
        assert result["child_count"] == 2

    def test_session_records_schema_and_timestamps(self, sdir: Path):
        state.add_nodes(sdir, parent="root", nodes=_nodes("NAME"))
        doc = json.loads((sdir / "session.json").read_text(encoding="utf-8"))

        assert doc["schema"] == "as-man/v1"
        assert doc["created"] and doc["updated"]

    def test_reading_a_missing_session_is_a_contract_violation(self, sdir: Path):
        with pytest.raises(ContractViolationError):
            state.outline(sdir, under="root")


class TestAddNodes:
    def test_generated_ids_are_unique_and_stable(self, sdir: Path):
        result = state.add_nodes(sdir, parent="root", nodes=_nodes("NAME", "SYNOPSIS", "NAME"))

        assert len(set(result["added"])) == 3

    def test_explicit_ids_are_preserved(self, sdir: Path):
        result = state.add_nodes(
            sdir, parent="root", nodes=[{"id": "ch12", "heading": "Recursive Queries", "promise": "p"}]
        )

        assert result["added"] == ["ch12"]

    def test_children_land_one_level_below_their_parent(self, sdir: Path):
        state.add_nodes(sdir, parent="root", nodes=[{"id": "p1", "heading": "Part 1", "promise": "p"}])
        state.add_nodes(sdir, parent="p1", nodes=[{"id": "c1", "heading": "Chapter 1", "promise": "p"}])

        child = state.outline(sdir, under="p1")["children"][0]
        assert child["level"] == 2

    def test_enumerating_children_marks_the_parent_enumerated(self, sdir: Path):
        state.add_nodes(sdir, parent="root", nodes=[{"id": "p1", "heading": "Part 1", "promise": "p"}])
        state.add_nodes(sdir, parent="p1", nodes=_nodes("Chapter 1"))

        assert state.enter(sdir, node_id="p1")["node"]["status"] == "enumerated"

    def test_unknown_parent_is_rejected(self, sdir: Path):
        state.add_nodes(sdir, parent="root", nodes=_nodes("NAME"))

        with pytest.raises(ContractViolationError):
            state.add_nodes(sdir, parent="nope", nodes=_nodes("X"))

    def test_empty_node_list_is_rejected(self, sdir: Path):
        with pytest.raises(ContractViolationError):
            state.add_nodes(sdir, parent="root", nodes=[])

    def test_blank_heading_is_rejected(self, sdir: Path):
        with pytest.raises(ContractViolationError):
            state.add_nodes(sdir, parent="root", nodes=[{"heading": "  ", "promise": "p"}])

    def test_missing_promise_is_rejected(self, sdir: Path):
        with pytest.raises(ContractViolationError):
            state.add_nodes(sdir, parent="root", nodes=[{"heading": "NAME"}])

    def test_duplicate_id_is_rejected(self, sdir: Path):
        state.add_nodes(sdir, parent="root", nodes=[{"id": "a", "heading": "A", "promise": "p"}])

        with pytest.raises(ContractViolationError):
            state.add_nodes(sdir, parent="root", nodes=[{"id": "a", "heading": "B", "promise": "p"}])


class TestOutlineIsBounded:
    def test_outline_returns_only_the_named_level(self, sdir: Path):
        state.add_nodes(sdir, parent="root", nodes=[{"id": "p1", "heading": "Part 1", "promise": "p"}])
        state.add_nodes(sdir, parent="p1", nodes=_nodes("Chapter 1", "Chapter 2"))

        top = state.outline(sdir, under="root")

        assert [c["id"] for c in top["children"]] == ["p1"]

    def test_children_carry_position_and_sibling_count(self, sdir: Path):
        state.add_nodes(sdir, parent="root", nodes=_nodes("A", "B", "C"))

        children = state.outline(sdir, under="root")["children"]

        assert [c["position"] for c in children] == [1, 2, 3]
        assert {c["sibling_count"] for c in children} == {3}

    def test_outline_never_includes_body_text(self, sdir: Path):
        state.add_nodes(sdir, parent="root", nodes=_nodes("A"))

        child = state.outline(sdir, under="root")["children"][0]

        assert "content" not in child and "body" not in child


class TestEnterAndNavigation:
    @pytest.fixture()
    def three(self, sdir: Path) -> Path:
        state.add_nodes(
            sdir,
            parent="root",
            nodes=[
                {"id": "a", "heading": "A", "promise": "p"},
                {"id": "b", "heading": "B", "promise": "p"},
                {"id": "c", "heading": "C", "promise": "p"},
            ],
        )
        return sdir

    def test_enter_reports_neighbours_for_next_and_previous(self, three: Path):
        result = state.enter(three, node_id="b")

        assert result["prev_id"] == "a"
        assert result["next_id"] == "c"

    def test_first_node_has_no_previous(self, three: Path):
        assert state.enter(three, node_id="a")["prev_id"] is None

    def test_last_node_has_no_next_and_is_the_end(self, three: Path):
        result = state.enter(three, node_id="c")

        assert result["next_id"] is None
        assert result["is_end"] is True

    def test_enter_reports_the_last_sibling_for_jump_to_end(self, three: Path):
        assert state.enter(three, node_id="a")["last_sibling_id"] == "c"

    def test_enter_reports_the_parent_for_up_a_level(self, sdir: Path):
        state.add_nodes(sdir, parent="root", nodes=[{"id": "p1", "heading": "P", "promise": "p"}])
        state.add_nodes(sdir, parent="p1", nodes=[{"id": "c1", "heading": "C", "promise": "p"}])

        assert state.enter(sdir, node_id="c1")["parent_id"] == "p1"

    def test_entering_records_the_trail_in_order(self, three: Path):
        state.enter(three, node_id="a")
        state.enter(three, node_id="c")
        state.enter(three, node_id="b")

        assert [step["id"] for step in state.trail(three)["trail"]] == ["a", "c", "b"]

    def test_entering_sets_the_current_node(self, three: Path):
        state.enter(three, node_id="b")

        assert state.status(three)["current"] == "b"

    def test_next_action_reflects_status(self, three: Path):
        assert state.enter(three, node_id="a")["next_action"] == "realise"

        state.realise(three, node_id="a", line_start=1, line_end=4)

        assert state.enter(three, node_id="a")["next_action"] == "render"

    def test_entering_an_unknown_node_is_rejected(self, three: Path):
        with pytest.raises(ContractViolationError):
            state.enter(three, node_id="zzz")


class TestGoToPosition:
    @pytest.fixture()
    def book(self, sdir: Path) -> Path:
        state.add_nodes(
            sdir,
            parent="root",
            nodes=[{"id": f"ch{i}", "heading": f"Chapter {i}", "promise": "p"} for i in range(1, 28)],
        )
        state.add_nodes(
            sdir,
            parent="ch12",
            nodes=[{"id": "s1", "heading": "First", "promise": "p"},
                   {"id": "s2", "heading": "Second", "promise": "p"}],
        )
        return sdir

    def test_jump_by_position_lands_on_that_entry(self, book: Path):
        result = state.enter(book, position=12, under="root")

        assert result["node"]["id"] == "ch12"
        assert result["node"]["position"] == 12

    def test_jump_by_position_is_one_based(self, book: Path):
        assert state.enter(book, position=1, under="root")["node"]["id"] == "ch1"

    def test_jump_defaults_to_the_current_level(self, book: Path):
        state.enter(book, node_id="ch5")

        assert state.enter(book, position=20)["node"]["id"] == "ch20"

    def test_jump_within_a_chapter_uses_that_parent(self, book: Path):
        assert state.enter(book, position=2, under="ch12")["node"]["id"] == "s2"

    def test_jump_past_the_end_is_rejected_with_the_valid_range(self, book: Path):
        with pytest.raises(ContractViolationError) as excinfo:
            state.enter(book, position=99, under="root")

        assert "27" in str(excinfo.value)

    def test_position_must_be_positive(self, book: Path):
        with pytest.raises(ContractViolationError):
            state.enter(book, position=0, under="root")

    def test_id_and_position_are_mutually_exclusive(self, book: Path):
        with pytest.raises(ContractViolationError):
            state.enter(book, node_id="ch1", position=1, under="root")

    def test_one_selector_is_required(self, book: Path):
        with pytest.raises(ContractViolationError):
            state.enter(book)

    def test_jump_with_no_current_node_and_no_parent_is_rejected(self, book: Path):
        with pytest.raises(ContractViolationError):
            state.enter(book, position=3)

    def test_a_jump_records_the_trail_like_any_other_move(self, book: Path):
        state.enter(book, position=12, under="root")

        assert state.trail(book)["trail"][-1]["id"] == "ch12"

    def test_a_jump_reports_neighbours_for_onward_navigation(self, book: Path):
        result = state.enter(book, position=12, under="root")

        assert result["prev_id"] == "ch11"
        assert result["next_id"] == "ch13"


class TestRealise:
    @pytest.fixture()
    def one(self, sdir: Path) -> Path:
        state.add_nodes(sdir, parent="root", nodes=[{"id": "a", "heading": "A", "promise": "p"}])
        return sdir

    def test_realise_records_the_line_span(self, one: Path):
        result = state.realise(one, node_id="a", line_start=10, line_end=42)

        assert result["node"]["line_start"] == 10
        assert result["node"]["line_end"] == 42
        assert result["node"]["status"] == "realised"

    def test_line_numbers_must_be_positive(self, one: Path):
        with pytest.raises(ContractViolationError):
            state.realise(one, node_id="a", line_start=0, line_end=4)

    def test_line_span_must_be_ordered(self, one: Path):
        with pytest.raises(ContractViolationError):
            state.realise(one, node_id="a", line_start=9, line_end=4)


class TestDetailLevel:
    @pytest.fixture()
    def page(self, sdir: Path) -> Path:
        state.add_nodes(
            sdir,
            parent="root",
            nodes=[{"id": "a", "heading": "A", "promise": "p"},
                   {"id": "b", "heading": "B", "promise": "p"}],
        )
        return sdir

    def test_a_node_starts_terse(self, page: Path):
        assert state.enter(page, node_id="a")["node"]["detail"] == "terse"

    def test_the_page_default_is_recorded(self, sdir: Path):
        state.describe(sdir, detail="full")

        assert state.status(sdir)["detail"] == "full"

    def test_new_nodes_inherit_the_page_default(self, sdir: Path):
        state.describe(sdir, detail="tutorial")
        state.add_nodes(sdir, parent="root", nodes=[{"id": "a", "heading": "A", "promise": "p"}])

        assert state.enter(sdir, node_id="a")["node"]["detail"] == "tutorial"

    def test_an_invalid_page_default_is_rejected(self, sdir: Path):
        with pytest.raises(ContractViolationError):
            state.describe(sdir, detail="chatty")

    def test_more_moves_one_step_up_the_ladder(self, page: Path):
        result = state.detail(page, node_id="a", more=True)

        assert result["from_detail"] == "terse"
        assert result["to_detail"] == "full"

    def test_less_moves_one_step_down(self, page: Path):
        state.detail(page, node_id="a", level="tutorial")

        assert state.detail(page, node_id="a", less=True)["to_detail"] == "full"

    def test_an_explicit_level_can_be_set(self, page: Path):
        assert state.detail(page, node_id="a", level="tutorial")["to_detail"] == "tutorial"

    def test_more_at_the_top_is_rejected_and_names_the_level(self, page: Path):
        state.detail(page, node_id="a", level="tutorial")

        with pytest.raises(ContractViolationError) as excinfo:
            state.detail(page, node_id="a", more=True)

        assert "tutorial" in str(excinfo.value)

    def test_less_at_the_bottom_is_rejected(self, page: Path):
        with pytest.raises(ContractViolationError):
            state.detail(page, node_id="a", less=True)

    def test_exactly_one_selector_is_required(self, page: Path):
        with pytest.raises(ContractViolationError):
            state.detail(page, node_id="a")
        with pytest.raises(ContractViolationError):
            state.detail(page, node_id="a", more=True, less=True)

    def test_an_unknown_level_is_rejected(self, page: Path):
        with pytest.raises(ContractViolationError):
            state.detail(page, node_id="a", level="exhaustive")

    def test_changing_detail_only_affects_that_node(self, page: Path):
        state.detail(page, node_id="a", level="tutorial")

        assert state.enter(page, node_id="b")["node"]["detail"] == "terse"

    def test_changing_detail_asks_for_a_rewrite(self, page: Path):
        assert state.detail(page, node_id="a", more=True)["next_action"] == "realise"

    def test_a_body_written_at_a_stale_level_is_rewritten_on_entry(self, page: Path):
        state.realise(page, node_id="a", line_start=1, line_end=4)
        assert state.enter(page, node_id="a")["next_action"] == "render"

        state.detail(page, node_id="a", more=True)

        assert state.enter(page, node_id="a")["next_action"] == "realise"

    def test_rewriting_at_the_new_level_settles_the_node(self, page: Path):
        state.realise(page, node_id="a", line_start=1, line_end=4)
        state.detail(page, node_id="a", more=True)
        state.realise(page, node_id="a", line_start=1, line_end=12)

        result = state.enter(page, node_id="a")
        assert result["next_action"] == "render"
        assert result["node"]["detail"] == "full"

    def test_realise_can_state_the_level_it_wrote(self, page: Path):
        state.realise(page, node_id="a", line_start=1, line_end=9, detail="tutorial")

        assert state.enter(page, node_id="a")["node"]["detail"] == "tutorial"

    def test_quiz_citations_follow_the_expanded_body(self, page: Path):
        state.realise(page, node_id="a", line_start=1, line_end=4)
        state.quiz_add(page, questions=[
            {"id": "q1", "node_id": "a", "type": "recall", "question": "q?", "answer_key": "k"}])
        state.detail(page, node_id="a", more=True)
        state.realise(page, node_id="a", line_start=1, line_end=20)

        picked = state.quiz_next(page, count=1)["questions"][0]
        assert picked["line_end"] == 20


class TestQuizCoversOnlyRealisedNodes:
    @pytest.fixture()
    def read_one(self, sdir: Path) -> Path:
        state.add_nodes(
            sdir,
            parent="root",
            nodes=[
                {"id": "a", "heading": "A", "promise": "p"},
                {"id": "b", "heading": "B", "promise": "p"},
            ],
        )
        state.realise(sdir, node_id="a", line_start=1, line_end=8)
        return sdir

    def test_questions_on_unrealised_nodes_are_rejected(self, read_one: Path):
        with pytest.raises(ContractViolationError):
            state.quiz_add(
                read_one,
                questions=[{"node_id": "b", "type": "recall", "question": "q?", "answer_key": "k"}],
            )

    def test_questions_on_realised_nodes_are_accepted(self, read_one: Path):
        result = state.quiz_add(
            read_one,
            questions=[{"node_id": "a", "type": "recall", "question": "q?", "answer_key": "k"}],
        )

        assert result["added_count"] == 1

    def test_unknown_question_type_is_rejected(self, read_one: Path):
        with pytest.raises(ContractViolationError):
            state.quiz_add(
                read_one,
                questions=[{"node_id": "a", "type": "vibes", "question": "q?", "answer_key": "k"}],
            )

    def test_next_returns_an_unasked_question_with_its_citation_span(self, read_one: Path):
        state.quiz_add(
            read_one,
            questions=[{"id": "q1", "node_id": "a", "type": "recall", "question": "q?", "answer_key": "k"}],
        )

        picked = state.quiz_next(read_one, count=1)["questions"][0]

        assert picked["id"] == "q1"
        assert picked["heading"] == "A"
        assert picked["line_start"] == 1 and picked["line_end"] == 8

    def test_next_never_repeats_an_answered_question(self, read_one: Path):
        state.quiz_add(
            read_one,
            questions=[
                {"id": "q1", "node_id": "a", "type": "recall", "question": "q1?", "answer_key": "k"},
                {"id": "q2", "node_id": "a", "type": "trap", "question": "q2?", "answer_key": "k"},
            ],
        )
        state.quiz_record(read_one, question_id="q1", verdict="correct")

        assert state.quiz_next(read_one, count=2)["questions"][0]["id"] == "q2"

    def test_next_is_empty_when_every_question_is_answered(self, read_one: Path):
        state.quiz_add(
            read_one,
            questions=[{"id": "q1", "node_id": "a", "type": "recall", "question": "q?", "answer_key": "k"}],
        )
        state.quiz_record(read_one, question_id="q1", verdict="correct")

        assert state.quiz_next(read_one, count=1)["questions"] == []

    def test_invalid_verdict_is_rejected(self, read_one: Path):
        state.quiz_add(
            read_one,
            questions=[{"id": "q1", "node_id": "a", "type": "recall", "question": "q?", "answer_key": "k"}],
        )

        with pytest.raises(ContractViolationError):
            state.quiz_record(read_one, question_id="q1", verdict="great")

    def test_recording_an_unknown_question_is_rejected(self, read_one: Path):
        with pytest.raises(ContractViolationError):
            state.quiz_record(read_one, question_id="nope", verdict="correct")


class TestQuizSelectionFavoursWeakNodes:
    @pytest.fixture()
    def two_read(self, sdir: Path) -> Path:
        state.add_nodes(
            sdir,
            parent="root",
            nodes=[
                {"id": "a", "heading": "A", "promise": "p"},
                {"id": "b", "heading": "B", "promise": "p"},
            ],
        )
        state.realise(sdir, node_id="a", line_start=1, line_end=8)
        state.realise(sdir, node_id="b", line_start=9, line_end=20)
        state.quiz_add(
            sdir,
            questions=[
                {"id": "a1", "node_id": "a", "type": "recall", "question": "a1?", "answer_key": "k"},
                {"id": "a2", "node_id": "a", "type": "transfer", "question": "a2?", "answer_key": "k"},
                {"id": "b1", "node_id": "b", "type": "recall", "question": "b1?", "answer_key": "k"},
                {"id": "b2", "node_id": "b", "type": "transfer", "question": "b2?", "answer_key": "k"},
            ],
        )
        return sdir

    def test_selection_shifts_to_the_node_the_reader_got_wrong(self, two_read: Path):
        state.quiz_record(two_read, question_id="a1", verdict="correct")
        state.quiz_record(two_read, question_id="b1", verdict="incorrect")

        assert state.quiz_next(two_read, count=1)["questions"][0]["node_id"] == "b"

    def test_report_counts_verdicts_per_node(self, two_read: Path):
        state.quiz_record(two_read, question_id="a1", verdict="correct")
        state.quiz_record(two_read, question_id="b1", verdict="incorrect")
        state.quiz_record(two_read, question_id="b2", verdict="partial")

        by_node = {row["node_id"]: row for row in state.quiz_report(two_read)["by_node"]}

        assert by_node["a"]["correct"] == 1
        assert by_node["b"]["incorrect"] == 1
        assert by_node["b"]["partial"] == 1

    def test_report_names_weak_nodes_to_re_read(self, two_read: Path):
        state.quiz_record(two_read, question_id="a1", verdict="correct")
        state.quiz_record(two_read, question_id="b1", verdict="incorrect")

        assert "b" in state.quiz_report(two_read)["weak_nodes"]


class TestGaps:
    @pytest.fixture()
    def ready(self, sdir: Path) -> Path:
        state.add_nodes(sdir, parent="root", nodes=[{"id": "a", "heading": "A", "promise": "p"}])
        return sdir

    def _gap(self, fingerprint: str = "egress-cost") -> dict:
        return {
            "fingerprint": fingerprint,
            "kind": "omission",
            "materiality": "high",
            "title": "Egress cost is not mentioned",
            "missing": "Cross-zone traffic is billed per gigabyte.",
            "effect": "The reader underestimates cost.",
            "evidence": "https://example.invalid/pricing (retrieved 2026-09-05)",
        }

    def test_gaps_are_deduplicated_by_fingerprint(self, ready: Path):
        state.gaps_add(ready, gaps=[self._gap()])
        result = state.gaps_add(ready, gaps=[self._gap()])

        assert result["added_count"] == 0
        assert len(state.gaps_list(ready)["gaps"]) == 1

    def test_distinct_fingerprints_accumulate(self, ready: Path):
        state.gaps_add(ready, gaps=[self._gap("one")])
        state.gaps_add(ready, gaps=[self._gap("two")])

        assert len(state.gaps_list(ready)["gaps"]) == 2

    def test_unknown_gap_kind_is_rejected(self, ready: Path):
        bad = self._gap()
        bad["kind"] = "hunch"

        with pytest.raises(ContractViolationError):
            state.gaps_add(ready, gaps=[bad])

    def test_unknown_materiality_is_rejected(self, ready: Path):
        bad = self._gap()
        bad["materiality"] = "vast"

        with pytest.raises(ContractViolationError):
            state.gaps_add(ready, gaps=[bad])

    def test_a_gap_without_evidence_is_marked_unverified(self, ready: Path):
        bare = self._gap()
        del bare["evidence"]

        state.gaps_add(ready, gaps=[bare])

        assert state.gaps_list(ready)["gaps"][0]["verified"] is False

    def test_a_gap_with_evidence_is_marked_verified(self, ready: Path):
        state.gaps_add(ready, gaps=[self._gap()])

        assert state.gaps_list(ready)["gaps"][0]["verified"] is True


class TestStatus:
    def test_status_summarises_progress_without_dumping_the_tree(self, sdir: Path):
        state.add_nodes(sdir, parent="root", nodes=_nodes("A", "B", "C"))
        state.realise(sdir, node_id=state.outline(sdir, under="root")["children"][0]["id"],
                      line_start=1, line_end=5)

        result = state.status(sdir)

        assert result["node_count"] == 4  # root plus three children
        assert result["realised_count"] == 1
        assert "nodes" not in result
