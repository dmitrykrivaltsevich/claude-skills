#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""KB graph — extract wikilink graph from knowledge base files.

Parses all .md files in knowledge/ and sources/, extracts [[wikilinks]],
and builds a directed adjacency list.  Returns JSON with nodes (including
type, degree), edges, connected components count, and dangling targets.

This is a data pipe — it computes the raw graph structure.
The LLM interprets topological meaning.

Output: JSON to stdout.  Errors to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from artifact_output import emit_json_result
from contracts import ContractViolationError, precondition

# Wikilink pattern: [[target]] or [[target|display text]]
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _category_for_path(fpath: Path, root: Path) -> str:
    """Determine the category (directory name under knowledge/ or sources/)."""
    try:
        rel = fpath.relative_to(root)
    except ValueError:
        return "unknown"
    parts = rel.parts
    # knowledge/entities/foo.md → "entities"
    # sources/references/foo.md → "sources"
    if len(parts) >= 2:
        if parts[0] == "sources":
            return "sources"
        return parts[1]
    return "unknown"


def _find_components(adj: dict[str, set[str]], all_nodes: set[str]) -> int:
    """Count connected components treating the graph as undirected."""
    visited: set[str] = set()
    # Build undirected adjacency
    undirected: dict[str, set[str]] = {n: set() for n in all_nodes}
    for src, targets in adj.items():
        for tgt in targets:
            if tgt in all_nodes:
                undirected[src].add(tgt)
                undirected[tgt].add(src)

    components = 0
    for node in all_nodes:
        if node in visited:
            continue
        components += 1
        stack = [node]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            for neighbour in undirected.get(current, set()):
                if neighbour not in visited:
                    stack.append(neighbour)
    return components


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@precondition(
    lambda kb_path, **_: len(kb_path.strip()) > 0,
    "kb_path must be non-empty",
)
def build_graph(kb_path: str) -> dict:
    """Extract the wikilink graph from a knowledge base.

    Returns a dict with:
      - nodes: list of {id, type, in_degree, out_degree, title}
      - edges: list of {source, target}
      - total_nodes, total_edges
      - components: number of connected components (undirected)
      - dangling_targets: list of wikilink targets with no matching file
    """
    root = Path(kb_path)
    knowledge_dir = root / "knowledge"
    sources_dir = root / "sources"

    # Collect all .md files: stem → (path, category)
    file_map: dict[str, tuple[Path, str]] = {}

    if knowledge_dir.exists():
        for fpath in knowledge_dir.rglob("*.md"):
            cat = _category_for_path(fpath, root)
            file_map[fpath.stem] = (fpath, cat)

    if sources_dir.exists():
        for fpath in sources_dir.rglob("*.md"):
            file_map[fpath.stem] = (fpath, "sources")

    if not file_map:
        return {
            "nodes": [],
            "edges": [],
            "total_nodes": 0,
            "total_edges": 0,
            "components": 0,
            "dangling_targets": [],
        }

    # Build directed adjacency: source_stem → set of target_stems
    adjacency: dict[str, set[str]] = {stem: set() for stem in file_map}
    dangling: set[str] = set()

    for stem, (fpath, _cat) in file_map.items():
        try:
            text = fpath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        targets = _WIKILINK_RE.findall(text)
        for raw_target in targets:
            target = raw_target.strip()
            if target == stem:
                continue  # skip self-links
            if target in file_map:
                adjacency[stem].add(target)
            else:
                dangling.add(target)

    # Compute degrees
    in_degree: dict[str, int] = {stem: 0 for stem in file_map}
    for src, targets in adjacency.items():
        for tgt in targets:
            in_degree[tgt] = in_degree.get(tgt, 0) + 1

    # Build nodes list
    nodes: list[dict] = []
    for stem, (fpath, cat) in sorted(file_map.items()):
        # Extract title
        title = stem
        try:
            text = fpath.read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
        except (OSError, UnicodeDecodeError):
            pass

        nodes.append({
            "id": stem,
            "type": cat,
            "title": title,
            "in_degree": in_degree.get(stem, 0),
            "out_degree": len(adjacency.get(stem, set())),
        })

    # Build edges list
    edges: list[dict] = []
    for src in sorted(adjacency):
        for tgt in sorted(adjacency[src]):
            edges.append({"source": src, "target": tgt})

    # Connected components (undirected)
    components = _find_components(adjacency, set(file_map.keys()))

    return {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "components": components,
        "dangling_targets": sorted(dangling),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extract KB wikilink graph")
    parser.add_argument("--path", required=True, help="Path to KB root")
    parser.add_argument(
        "--output", "-o", type=Path,
        help="Write full JSON results to this file and emit a compact artifact envelope on stdout",
    )
    args = parser.parse_args(argv)

    try:
        result = build_graph(args.path)
    except ContractViolationError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)

    emit_json_result(result, output_path=args.output, artifact_kind="kb-graph")


if __name__ == "__main__":
    main()
