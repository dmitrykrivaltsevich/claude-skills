#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""KB topology — graph-theoretic analysis of knowledge base structure.

Takes the raw graph from graph.py and computes topological metrics:
  - Degree distribution & anomalies (isolated, under-linked authority nodes)
  - Betweenness centrality (bridge/hub detection)
  - Community detection (label propagation — no external deps)
  - Structural holes (disconnected cluster pairs)
  - Reciprocity (fraction of bidirectional edges)
  - Category distribution

All algorithms use only stdlib — no networkx, no numpy.
The LLM interprets what the metrics mean for the knowledge domain.

Output: JSON to stdout.  Errors to stderr.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from contracts import ContractViolationError, precondition
from graph import build_graph


# ---------------------------------------------------------------------------
# Graph algorithms (stdlib-only)
# ---------------------------------------------------------------------------

def _undirected_adj(nodes: list[dict], edges: list[dict]) -> dict[str, set[str]]:
    """Build undirected adjacency from directed edges."""
    adj: dict[str, set[str]] = {n["id"]: set() for n in nodes}
    for e in edges:
        adj[e["source"]].add(e["target"])
        adj[e["target"]].add(e["source"])
    return adj


def _directed_adj(nodes: list[dict], edges: list[dict]) -> dict[str, set[str]]:
    """Build directed adjacency (outgoing only)."""
    adj: dict[str, set[str]] = {n["id"]: set() for n in nodes}
    for e in edges:
        adj[e["source"]].add(e["target"])
    return adj


def _bfs_shortest_paths(adj: dict[str, set[str]], source: str) -> dict[str, tuple[int, list[list[str]]]]:
    """BFS from source.  Returns {node: (distance, [paths])} for all reachable nodes.

    Paths are lists of intermediate nodes (excluding source and target).
    Only used for betweenness — keeps all shortest paths to get accurate counts.
    """
    dist: dict[str, int] = {source: 0}
    # predecessors: node → list of predecessors on shortest paths
    preds: dict[str, list[str]] = {source: []}
    queue = collections.deque([source])

    while queue:
        current = queue.popleft()
        for neighbour in adj.get(current, set()):
            if neighbour not in dist:
                dist[neighbour] = dist[current] + 1
                preds[neighbour] = [current]
                queue.append(neighbour)
            elif dist[neighbour] == dist[current] + 1:
                preds[neighbour].append(current)

    return dist, preds


def _betweenness_centrality(adj: dict[str, set[str]], node_ids: list[str]) -> dict[str, float]:
    """Brandes algorithm for betweenness centrality on undirected graph.

    Returns normalized centrality (divided by (n-1)(n-2)/2 for undirected).
    """
    centrality: dict[str, float] = {n: 0.0 for n in node_ids}
    n = len(node_ids)

    for s in node_ids:
        # BFS
        stack: list[str] = []
        preds: dict[str, list[str]] = {n: [] for n in node_ids}
        sigma: dict[str, int] = {n: 0 for n in node_ids}
        sigma[s] = 1
        dist: dict[str, int] = {n: -1 for n in node_ids}
        dist[s] = 0
        queue = collections.deque([s])

        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in adj.get(v, set()):
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    queue.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    preds[w].append(v)

        # Accumulation
        delta: dict[str, float] = {n: 0.0 for n in node_ids}
        while stack:
            w = stack.pop()
            for v in preds[w]:
                if sigma[w] > 0:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
            if w != s:
                centrality[w] += delta[w]

    # Normalize for undirected graph: each pair counted from both ends
    # so divide by 2, then by (n-1)(n-2) if n > 2
    if n > 2:
        norm = (n - 1) * (n - 2)
        for node in centrality:
            centrality[node] = centrality[node] / norm
    elif n <= 2:
        for node in centrality:
            centrality[node] = 0.0

    return centrality


def _label_propagation_communities(adj: dict[str, set[str]], node_ids: list[str],
                                    seed: int = 42) -> list[list[str]]:
    """Simple label propagation community detection.

    Each node starts with its own label. In each iteration, each node adopts
    the most frequent label among its neighbours. Converges when no node changes.

    Deterministic with fixed random seed for reproducibility.
    """
    rng = random.Random(seed)

    if not node_ids:
        return []

    # Assign initial labels
    labels: dict[str, int] = {n: i for i, n in enumerate(node_ids)}

    # Iterate until convergence (max 100 iterations to avoid infinite loop)
    # 100 iterations is sufficient for convergence on KB-sized graphs
    # (typically < 10k nodes); label propagation converges in O(sqrt(n)) steps.
    for _ in range(100):
        changed = False
        order = list(node_ids)
        rng.shuffle(order)

        for node in order:
            neighbours = adj.get(node, set())
            if not neighbours:
                continue

            # Count neighbour labels
            label_counts: dict[int, int] = {}
            for nb in neighbours:
                lbl = labels[nb]
                label_counts[lbl] = label_counts.get(lbl, 0) + 1

            max_count = max(label_counts.values())
            candidates = [lbl for lbl, cnt in label_counts.items() if cnt == max_count]
            # Pick smallest label among ties for determinism
            best = min(candidates)

            if labels[node] != best:
                labels[node] = best
                changed = True

        if not changed:
            break

    # Group nodes by label
    communities: dict[int, list[str]] = {}
    for node, label in labels.items():
        communities.setdefault(label, []).append(node)

    # Sort for determinism: by size descending, then by first member
    result = sorted(communities.values(), key=lambda c: (-len(c), c[0]))
    return result


def _find_connected_components(adj: dict[str, set[str]], node_ids: list[str]) -> list[list[str]]:
    """Find connected components using undirected adjacency."""
    visited: set[str] = set()
    components: list[list[str]] = []

    for start in node_ids:
        if start in visited:
            continue
        component: list[str] = []
        stack = [start]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            for nb in adj.get(node, set()):
                if nb not in visited:
                    stack.append(nb)
        components.append(sorted(component))

    return sorted(components, key=lambda c: (-len(c), c[0]))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@precondition(
    lambda kb_path, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
def analyze_topology(kb_path: str) -> dict:
    """Analyze the topological structure of a knowledge base graph.

    Runs graph.py to extract the raw graph, then computes:
      - Summary stats (nodes, edges, density, avg degree, reciprocity)
      - Category distribution
      - Community clusters (label propagation)
      - Bridge nodes (high betweenness centrality)
      - Structural holes (disconnected component pairs)
      - Degree anomalies (isolated, under-linked authority nodes)
      - Top betweenness centrality nodes
    """
    graph = build_graph(kb_path)
    nodes = graph["nodes"]
    edges = graph["edges"]

    if not nodes:
        return {
            "total_nodes": 0,
            "total_edges": 0,
            "components": 0,
            "density": 0.0,
            "avg_degree": 0.0,
            "reciprocity": 0.0,
            "category_distribution": {},
            "clusters": [],
            "bridges": [],
            "structural_holes": [],
            "degree_anomalies": [],
            "top_betweenness": [],
        }

    n = len(nodes)
    m = len(edges)
    node_ids = [nd["id"] for nd in nodes]
    nodes_by_id = {nd["id"]: nd for nd in nodes}

    # --- Summary stats ---

    # Density: m / (n * (n-1)) for directed graph
    density = m / (n * (n - 1)) if n > 1 else 0.0

    # Average degree (directed: count in + out / n)
    total_degree = sum(nd["in_degree"] + nd["out_degree"] for nd in nodes)
    avg_degree = total_degree / n if n > 0 else 0.0

    # Reciprocity: fraction of edges whose reverse also exists
    edge_set = {(e["source"], e["target"]) for e in edges}
    reciprocal_count = sum(1 for s, t in edge_set if (t, s) in edge_set)
    reciprocity = reciprocal_count / m if m > 0 else 0.0

    # --- Category distribution ---
    cat_dist: dict[str, int] = {}
    for nd in nodes:
        cat = nd["type"]
        cat_dist[cat] = cat_dist.get(cat, 0) + 1

    # --- Undirected adjacency for betweenness & communities ---
    u_adj = _undirected_adj(nodes, edges)

    # --- Betweenness centrality ---
    betweenness = _betweenness_centrality(u_adj, node_ids)

    # Top betweenness (nodes with centrality > 0, sorted desc, top 10)
    # 10 results is enough for the LLM to identify the most important
    # bridge nodes without overwhelming the output.
    top_betw = sorted(
        [{"id": nid, "betweenness": round(bc, 4), "type": nodes_by_id[nid]["type"],
          "title": nodes_by_id[nid]["title"]}
         for nid, bc in betweenness.items() if bc > 0],
        key=lambda x: -x["betweenness"],
    )[:10]

    # --- Community detection ---
    communities = _label_propagation_communities(u_adj, node_ids)

    clusters: list[dict] = []
    for i, members in enumerate(communities):
        if len(members) < 2:
            continue  # skip singleton communities
        # Determine dominant category
        cat_counts: dict[str, int] = {}
        for mid in members:
            cat = nodes_by_id[mid]["type"]
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        dominant_cat = max(cat_counts, key=cat_counts.get)
        clusters.append({
            "id": i,
            "size": len(members),
            "members": sorted(members),
            "dominant_category": dominant_cat,
            "category_breakdown": cat_counts,
        })

    # --- Bridge detection ---
    # Nodes with betweenness significantly above average
    avg_betw = sum(betweenness.values()) / n if n > 0 else 0.0
    # Threshold: 2× average betweenness — catches nodes that are genuinely
    # more central than typical, without flagging every node in a small graph.
    threshold = max(avg_betw * 2, 0.01)
    bridges = [
        {"id": nid, "betweenness": round(bc, 4), "type": nodes_by_id[nid]["type"],
         "title": nodes_by_id[nid]["title"]}
        for nid, bc in betweenness.items()
        if bc >= threshold
    ]
    bridges.sort(key=lambda x: -x["betweenness"])

    # --- Structural holes ---
    # Find connected components; pairs of components = structural holes
    components_list = _find_connected_components(u_adj, node_ids)
    structural_holes: list[dict] = []
    if len(components_list) > 1:
        for i in range(len(components_list)):
            for j in range(i + 1, len(components_list)):
                # Represent each component by its top members (by degree)
                def _top_members(comp: list[str], limit: int = 3) -> list[str]:
                    """Top members by total degree — shows the most connected
                    nodes to help the LLM quickly understand what each component
                    is about.  Limit 3 keeps output concise."""
                    return sorted(comp,
                                  key=lambda x: -(nodes_by_id[x]["in_degree"] + nodes_by_id[x]["out_degree"]))[:limit]

                structural_holes.append({
                    "cluster_a": _top_members(components_list[i]),
                    "cluster_b": _top_members(components_list[j]),
                    "size_a": len(components_list[i]),
                    "size_b": len(components_list[j]),
                })

    # --- Degree anomalies ---
    degree_anomalies: list[dict] = []
    for nd in nodes:
        total_deg = nd["in_degree"] + nd["out_degree"]
        if total_deg == 0:
            degree_anomalies.append({
                "id": nd["id"],
                "type": nd["type"],
                "title": nd["title"],
                "in_degree": nd["in_degree"],
                "out_degree": nd["out_degree"],
                "reason": "isolated",
            })
        elif nd["in_degree"] >= 3 and nd["out_degree"] == 0:
            # High authority (many incoming) but no outgoing = under-linked
            degree_anomalies.append({
                "id": nd["id"],
                "type": nd["type"],
                "title": nd["title"],
                "in_degree": nd["in_degree"],
                "out_degree": nd["out_degree"],
                "reason": "under-linked authority (many incoming, no outgoing)",
            })
        elif nd["out_degree"] >= 5 and nd["in_degree"] == 0:
            # High hub (many outgoing) but no incoming = orphan hub
            degree_anomalies.append({
                "id": nd["id"],
                "type": nd["type"],
                "title": nd["title"],
                "in_degree": nd["in_degree"],
                "out_degree": nd["out_degree"],
                "reason": "orphan hub (many outgoing, no incoming)",
            })

    degree_anomalies.sort(key=lambda x: x["id"])

    return {
        "total_nodes": n,
        "total_edges": m,
        "components": graph["components"],
        "density": round(density, 4),
        "avg_degree": round(avg_degree, 2),
        "reciprocity": round(reciprocity, 4),
        "category_distribution": dict(sorted(cat_dist.items())),
        "clusters": clusters,
        "bridges": bridges,
        "structural_holes": structural_holes,
        "degree_anomalies": degree_anomalies,
        "top_betweenness": top_betw,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze KB graph topology")
    parser.add_argument("--path", required=True, help="Path to KB root")
    args = parser.parse_args()

    try:
        result = analyze_topology(args.path)
    except ContractViolationError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
