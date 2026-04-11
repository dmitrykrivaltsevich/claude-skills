"""Tests for graph.py — KB wikilink graph extraction."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from graph import build_graph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scaffold(tmp_path: Path) -> Path:
    """Minimal KB scaffold with knowledge/ dir."""
    kb = tmp_path / "test-kb"
    (kb / "knowledge" / "entities").mkdir(parents=True)
    (kb / "knowledge" / "topics").mkdir(parents=True)
    (kb / "knowledge" / "ideas").mkdir(parents=True)
    (kb / "knowledge" / "citations").mkdir(parents=True)
    (kb / "knowledge" / "meta").mkdir(parents=True)
    (kb / "knowledge" / "questions").mkdir(parents=True)
    (kb / "sources" / "references").mkdir(parents=True)
    return kb


def _write(kb: Path, rel_path: str, content: str) -> None:
    """Write a file at the given path relative to kb root."""
    p = kb / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dedent(content).strip() + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests — build_graph
# ---------------------------------------------------------------------------

class TestBuildGraph:

    def test_empty_kb(self, tmp_path: Path) -> None:
        kb = _scaffold(tmp_path)
        result = build_graph(str(kb))
        assert result["total_nodes"] == 0
        assert result["total_edges"] == 0
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_single_node_no_links(self, tmp_path: Path) -> None:
        kb = _scaffold(tmp_path)
        _write(kb, "knowledge/entities/alice.md", """\
            ---
            type: entity
            ---
            # Alice
            No links here.
        """)
        result = build_graph(str(kb))
        assert result["total_nodes"] == 1
        assert result["total_edges"] == 0
        assert result["nodes"][0]["id"] == "alice"
        assert result["nodes"][0]["type"] == "entities"
        assert result["nodes"][0]["in_degree"] == 0
        assert result["nodes"][0]["out_degree"] == 0

    def test_simple_directed_edge(self, tmp_path: Path) -> None:
        kb = _scaffold(tmp_path)
        _write(kb, "knowledge/entities/alice.md", """\
            ---
            type: entity
            ---
            # Alice
            Works with [[bob]].
        """)
        _write(kb, "knowledge/entities/bob.md", """\
            ---
            type: entity
            ---
            # Bob
            Just Bob.
        """)
        result = build_graph(str(kb))
        assert result["total_nodes"] == 2
        assert result["total_edges"] == 1
        edges = result["edges"]
        assert edges[0]["source"] == "alice"
        assert edges[0]["target"] == "bob"

    def test_bidirectional_edges(self, tmp_path: Path) -> None:
        kb = _scaffold(tmp_path)
        _write(kb, "knowledge/entities/alice.md", """\
            ---
            type: entity
            ---
            # Alice
            Works with [[bob]].
        """)
        _write(kb, "knowledge/entities/bob.md", """\
            ---
            type: entity
            ---
            # Bob
            Also works with [[alice]].
        """)
        result = build_graph(str(kb))
        assert result["total_edges"] == 2
        # Both nodes should have in_degree=1, out_degree=1
        nodes_by_id = {n["id"]: n for n in result["nodes"]}
        assert nodes_by_id["alice"]["in_degree"] == 1
        assert nodes_by_id["alice"]["out_degree"] == 1
        assert nodes_by_id["bob"]["in_degree"] == 1
        assert nodes_by_id["bob"]["out_degree"] == 1

    def test_cross_category_links(self, tmp_path: Path) -> None:
        kb = _scaffold(tmp_path)
        _write(kb, "knowledge/entities/alice.md", """\
            ---
            type: entity
            ---
            # Alice
            Proposed [[attention-mechanism]].
        """)
        _write(kb, "knowledge/topics/attention-mechanism.md", """\
            ---
            type: topic
            ---
            # Attention Mechanism
            Proposed by [[alice]].
        """)
        result = build_graph(str(kb))
        assert result["total_nodes"] == 2
        assert result["total_edges"] == 2
        nodes_by_id = {n["id"]: n for n in result["nodes"]}
        assert nodes_by_id["alice"]["type"] == "entities"
        assert nodes_by_id["attention-mechanism"]["type"] == "topics"

    def test_dangling_links_excluded_from_edges(self, tmp_path: Path) -> None:
        """Links to non-existent pages are NOT edges (but tracked in dangling)."""
        kb = _scaffold(tmp_path)
        _write(kb, "knowledge/entities/alice.md", """\
            ---
            type: entity
            ---
            # Alice
            Knows [[ghost-person]] and [[bob]].
        """)
        _write(kb, "knowledge/entities/bob.md", """\
            ---
            type: entity
            ---
            # Bob
        """)
        result = build_graph(str(kb))
        assert result["total_edges"] == 1  # only alice→bob
        assert "ghost-person" in result["dangling_targets"]

    def test_self_links_excluded(self, tmp_path: Path) -> None:
        kb = _scaffold(tmp_path)
        _write(kb, "knowledge/entities/alice.md", """\
            ---
            type: entity
            ---
            # Alice
            See [[alice]] for more.
        """)
        result = build_graph(str(kb))
        assert result["total_edges"] == 0

    def test_multiple_links_same_target_counted_once(self, tmp_path: Path) -> None:
        kb = _scaffold(tmp_path)
        _write(kb, "knowledge/entities/alice.md", """\
            ---
            type: entity
            ---
            # Alice
            Works with [[bob]]. And again [[bob]]. And [[bob|Bobby]].
        """)
        _write(kb, "knowledge/entities/bob.md", """\
            ---
            type: entity
            ---
            # Bob
        """)
        result = build_graph(str(kb))
        # Multiple mentions of same target = one edge
        assert result["total_edges"] == 1

    def test_source_stubs_as_valid_targets(self, tmp_path: Path) -> None:
        """Source reference stubs should be valid nodes (link targets)."""
        kb = _scaffold(tmp_path)
        _write(kb, "knowledge/entities/alice.md", """\
            ---
            type: entity
            ---
            # Alice
            Published [[real-2020]].
        """)
        _write(kb, "sources/references/real-2020.md", """\
            ---
            type: source-ref
            ---
            # Real 2020
        """)
        result = build_graph(str(kb))
        # Source stubs included as nodes
        nodes_by_id = {n["id"]: n for n in result["nodes"]}
        assert "real-2020" in nodes_by_id
        assert nodes_by_id["real-2020"]["type"] == "sources"
        assert result["total_edges"] == 1

    def test_degree_counts(self, tmp_path: Path) -> None:
        """Hub node should have high out_degree, authority node high in_degree."""
        kb = _scaffold(tmp_path)
        _write(kb, "knowledge/meta/overview.md", """\
            ---
            type: meta
            ---
            # Overview
            See [[alice]], [[bob]], [[topic-x]].
        """)
        _write(kb, "knowledge/entities/alice.md", "---\ntype: entity\n---\n# Alice")
        _write(kb, "knowledge/entities/bob.md", "---\ntype: entity\n---\n# Bob")
        _write(kb, "knowledge/topics/topic-x.md", "---\ntype: topic\n---\n# X")
        result = build_graph(str(kb))
        nodes_by_id = {n["id"]: n for n in result["nodes"]}
        assert nodes_by_id["overview"]["out_degree"] == 3
        assert nodes_by_id["overview"]["in_degree"] == 0
        assert nodes_by_id["alice"]["in_degree"] == 1
        assert nodes_by_id["alice"]["out_degree"] == 0

    def test_connected_components(self, tmp_path: Path) -> None:
        """Two isolated clusters = 2 components."""
        kb = _scaffold(tmp_path)
        # Cluster 1
        _write(kb, "knowledge/entities/alice.md", "---\ntype: entity\n---\n# Alice\n[[bob]]")
        _write(kb, "knowledge/entities/bob.md", "---\ntype: entity\n---\n# Bob\n[[alice]]")
        # Cluster 2 (isolated)
        _write(kb, "knowledge/topics/topic-z.md", "---\ntype: topic\n---\n# Z\n[[idea-q]]")
        _write(kb, "knowledge/ideas/idea-q.md", "---\ntype: idea\n---\n# Q\n[[topic-z]]")
        result = build_graph(str(kb))
        assert result["total_nodes"] == 4
        assert result["components"] == 2

    def test_aliased_wikilinks_resolved(self, tmp_path: Path) -> None:
        """[[target|Display Text]] should resolve to 'target'."""
        kb = _scaffold(tmp_path)
        _write(kb, "knowledge/entities/alice.md", """\
            ---
            type: entity
            ---
            # Alice
            Met [[bob|Bob Smith]] at the conference.
        """)
        _write(kb, "knowledge/entities/bob.md", "---\ntype: entity\n---\n# Bob")
        result = build_graph(str(kb))
        assert result["total_edges"] == 1
        assert result["edges"][0]["target"] == "bob"


class TestGraphCli:

    def test_cli_json_output(self, tmp_path: Path) -> None:
        kb = _scaffold(tmp_path)
        _write(kb, "knowledge/entities/alice.md", "---\ntype: entity\n---\n# Alice\n[[bob]]")
        _write(kb, "knowledge/entities/bob.md", "---\ntype: entity\n---\n# Bob")
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "scripts" / "graph.py"),
             "--path", str(kb)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["total_nodes"] == 2
        assert data["total_edges"] == 1
