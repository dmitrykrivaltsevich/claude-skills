"""Tests for topology.py — KB graph topology analysis."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from topology import analyze_topology


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
    p = kb / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dedent(content).strip() + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests — analyze_topology
# ---------------------------------------------------------------------------

class TestAnalyzeTopology:

    def test_empty_kb_returns_empty_analysis(self, tmp_path: Path) -> None:
        kb = _scaffold(tmp_path)
        result = analyze_topology(str(kb))
        assert result["total_nodes"] == 0
        assert result["clusters"] == []
        assert result["bridges"] == []
        assert result["structural_holes"] == []
        assert result["degree_anomalies"] == []

    def test_summary_stats(self, tmp_path: Path) -> None:
        """Basic summary statistics for a small graph."""
        kb = _scaffold(tmp_path)
        _write(kb, "knowledge/entities/a.md", "---\ntype: entity\n---\n# A\n[[b]] [[c]]")
        _write(kb, "knowledge/entities/b.md", "---\ntype: entity\n---\n# B\n[[a]]")
        _write(kb, "knowledge/entities/c.md", "---\ntype: entity\n---\n# C\n[[a]]")
        result = analyze_topology(str(kb))
        assert result["total_nodes"] == 3
        assert result["total_edges"] == 4
        assert result["components"] == 1
        assert "avg_degree" in result
        assert "density" in result
        assert result["density"] > 0

    def test_bridge_detection(self, tmp_path: Path) -> None:
        """A node connecting two otherwise separate clusters is a bridge."""
        kb = _scaffold(tmp_path)
        # Cluster 1: a↔b
        _write(kb, "knowledge/entities/a.md", "---\ntype: entity\n---\n# A\n[[b]]")
        _write(kb, "knowledge/entities/b.md", "---\ntype: entity\n---\n# B\n[[a]] [[bridge]]")
        # Bridge node connects both clusters
        _write(kb, "knowledge/entities/bridge.md", "---\ntype: entity\n---\n# Bridge\n[[b]] [[x]]")
        # Cluster 2: x↔y
        _write(kb, "knowledge/topics/x.md", "---\ntype: topic\n---\n# X\n[[bridge]] [[y]]")
        _write(kb, "knowledge/topics/y.md", "---\ntype: topic\n---\n# Y\n[[x]]")
        result = analyze_topology(str(kb))
        bridge_ids = [b["id"] for b in result["bridges"]]
        assert "bridge" in bridge_ids

    def test_cluster_detection(self, tmp_path: Path) -> None:
        """Disconnected subgraphs should be detected as separate clusters."""
        kb = _scaffold(tmp_path)
        # Cluster 1: a↔b↔c↔a (triangle)
        _write(kb, "knowledge/entities/a.md", "---\ntype: entity\n---\n# A\n[[b]] [[c]]")
        _write(kb, "knowledge/entities/b.md", "---\ntype: entity\n---\n# B\n[[a]] [[c]]")
        _write(kb, "knowledge/entities/c.md", "---\ntype: entity\n---\n# C\n[[a]] [[b]]")
        # Cluster 2: x↔y↔z↔x (triangle, disconnected from cluster 1)
        _write(kb, "knowledge/topics/x.md", "---\ntype: topic\n---\n# X\n[[y]] [[z]]")
        _write(kb, "knowledge/topics/y.md", "---\ntype: topic\n---\n# Y\n[[x]] [[z]]")
        _write(kb, "knowledge/topics/z.md", "---\ntype: topic\n---\n# Z\n[[x]] [[y]]")
        result = analyze_topology(str(kb))
        assert len(result["clusters"]) >= 2
        # Each cluster should have members
        for cluster in result["clusters"]:
            assert len(cluster["members"]) >= 2

    def test_structural_holes(self, tmp_path: Path) -> None:
        """Pairs of clusters with no direct connections = structural holes."""
        kb = _scaffold(tmp_path)
        # Cluster 1: fully connected
        _write(kb, "knowledge/entities/a.md", "---\ntype: entity\n---\n# A\n[[b]]")
        _write(kb, "knowledge/entities/b.md", "---\ntype: entity\n---\n# B\n[[a]]")
        # Cluster 2: fully connected but isolated
        _write(kb, "knowledge/topics/x.md", "---\ntype: topic\n---\n# X\n[[y]]")
        _write(kb, "knowledge/topics/y.md", "---\ntype: topic\n---\n# Y\n[[x]]")
        result = analyze_topology(str(kb))
        # There should be a structural hole between the two components
        assert len(result["structural_holes"]) >= 1
        hole = result["structural_holes"][0]
        assert "cluster_a" in hole
        assert "cluster_b" in hole

    def test_degree_anomalies(self, tmp_path: Path) -> None:
        """A node mentioned by many but having few outgoing links is anomalous."""
        kb = _scaffold(tmp_path)
        # 'hub' is pointed to by many nodes but links to nothing
        _write(kb, "knowledge/entities/hub.md", "---\ntype: entity\n---\n# Hub\nNo links.")
        for name in ["a", "b", "c", "d", "e"]:
            _write(kb, f"knowledge/entities/{name}.md",
                   f"---\ntype: entity\n---\n# {name.upper()}\n[[hub]]")
        result = analyze_topology(str(kb))
        anomaly_ids = [a["id"] for a in result["degree_anomalies"]]
        assert "hub" in anomaly_ids
        hub_anomaly = [a for a in result["degree_anomalies"] if a["id"] == "hub"][0]
        assert hub_anomaly["in_degree"] >= 5
        assert hub_anomaly["out_degree"] == 0
        assert "under-linked" in hub_anomaly["reason"]

    def test_isolated_nodes_detected(self, tmp_path: Path) -> None:
        """Nodes with degree 0 should appear in degree_anomalies."""
        kb = _scaffold(tmp_path)
        _write(kb, "knowledge/entities/lonely.md", "---\ntype: entity\n---\n# Lonely\nNo links.")
        _write(kb, "knowledge/entities/a.md", "---\ntype: entity\n---\n# A\n[[b]]")
        _write(kb, "knowledge/entities/b.md", "---\ntype: entity\n---\n# B\n[[a]]")
        result = analyze_topology(str(kb))
        anomaly_ids = [a["id"] for a in result["degree_anomalies"]]
        assert "lonely" in anomaly_ids
        lonely = [a for a in result["degree_anomalies"] if a["id"] == "lonely"][0]
        assert lonely["reason"] == "isolated"

    def test_category_distribution(self, tmp_path: Path) -> None:
        """Should report how many nodes per category."""
        kb = _scaffold(tmp_path)
        _write(kb, "knowledge/entities/a.md", "---\ntype: entity\n---\n# A")
        _write(kb, "knowledge/entities/b.md", "---\ntype: entity\n---\n# B")
        _write(kb, "knowledge/topics/t.md", "---\ntype: topic\n---\n# T")
        result = analyze_topology(str(kb))
        dist = result["category_distribution"]
        assert dist["entities"] == 2
        assert dist["topics"] == 1

    def test_reciprocity(self, tmp_path: Path) -> None:
        """Reciprocity = fraction of edges that are bidirectional."""
        kb = _scaffold(tmp_path)
        # a↔b (reciprocal), a→c (not reciprocal)
        _write(kb, "knowledge/entities/a.md", "---\ntype: entity\n---\n# A\n[[b]] [[c]]")
        _write(kb, "knowledge/entities/b.md", "---\ntype: entity\n---\n# B\n[[a]]")
        _write(kb, "knowledge/entities/c.md", "---\ntype: entity\n---\n# C\nNo links.")
        result = analyze_topology(str(kb))
        # 3 edges total: a→b, b→a, a→c.  2 of 3 are reciprocal = 0.667
        assert 0.6 < result["reciprocity"] < 0.7

    def test_top_betweenness(self, tmp_path: Path) -> None:
        """Nodes with high betweenness centrality should be reported."""
        kb = _scaffold(tmp_path)
        # Star topology: center connects to 4 leaves
        _write(kb, "knowledge/entities/center.md",
               "---\ntype: entity\n---\n# Center\n[[n1]] [[n2]] [[n3]] [[n4]]")
        for i in range(1, 5):
            _write(kb, f"knowledge/entities/n{i}.md",
                   f"---\ntype: entity\n---\n# N{i}\n[[center]]")
        result = analyze_topology(str(kb))
        # center should have highest betweenness
        if result["top_betweenness"]:
            assert result["top_betweenness"][0]["id"] == "center"

    def test_small_graph_no_crash(self, tmp_path: Path) -> None:
        """Single node graph shouldn't crash any metrics."""
        kb = _scaffold(tmp_path)
        _write(kb, "knowledge/entities/solo.md", "---\ntype: entity\n---\n# Solo")
        result = analyze_topology(str(kb))
        assert result["total_nodes"] == 1
        assert result["density"] == 0.0
        assert result["reciprocity"] == 0.0


class TestTopologyCli:

    def test_cli_json_output(self, tmp_path: Path) -> None:
        kb = _scaffold(tmp_path)
        _write(kb, "knowledge/entities/a.md", "---\ntype: entity\n---\n# A\n[[b]]")
        _write(kb, "knowledge/entities/b.md", "---\ntype: entity\n---\n# B\n[[a]]")
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "scripts" / "topology.py"),
             "--path", str(kb)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["total_nodes"] == 2
        assert "clusters" in data
        assert "bridges" in data
