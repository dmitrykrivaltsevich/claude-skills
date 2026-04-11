# Topology Workflow — Graph-Theoretic Analysis

## Table of Contents

1. [Rationale](#rationale)
2. [When to Trigger](#when-to-trigger)
3. [Analysis Protocol](#analysis-protocol)
4. [Interpreting Metrics](#interpreting-metrics)
5. [Action Patterns](#action-patterns)
6. [Self-Diagnosis](#self-diagnosis)

## Rationale

The KB is a graph where entries are nodes and wikilinks are edges. This graph has **shape**, and shape has **meaning**:

- A dense cluster = well-covered topic area
- A bridge node = interdisciplinary connector (most valuable node in the graph)
- A structural hole = blind spot where knowledge should exist but doesn't
- A high-authority node with low out-degree = under-extracted entry (many things point to it, but it points nowhere — its full context isn't captured)
- An isolated node = knowledge orphan that needs integration

Scripts compute the metrics. **You interpret what they mean** for the knowledge domain. A "structural hole between cluster A and cluster B" is just topology — you decide whether it's a real gap worth filling or an expected boundary.

## When to Trigger

- User says "topology", "analyze structure", "where are the gaps", "what's missing"
- After `kb:lint` when looking for strategic (not just mechanical) improvements
- Periodically after adding 5+ sources — the graph shape changes
- When the user asks "what should I add next?" — topology reveals the highest-value gaps
- After `kb:iterate` discovers a question that topology can contextualize

## Analysis Protocol

### Step 1 — Extract Graph

```bash
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/graph.py --path <KB_PATH>
```

Read the output. Note: `total_nodes`, `total_edges`, `components`, `dangling_targets`.

### Step 2 — Analyze Topology

```bash
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/topology.py --path <KB_PATH>
```

Read the full JSON output. The key sections to interpret:

| Field | What it tells you |
|-------|-------------------|
| `density` | How interconnected the KB is overall (0 = no links, 1 = everything links to everything). Healthy KBs: 0.01–0.10 |
| `reciprocity` | Fraction of links that go both ways. Should be > 0.5 after lint. Low reciprocity = broken backlinks |
| `components` | Number of disconnected subgraphs. Should be 1 for a healthy KB. >1 = knowledge islands |
| `clusters` | Tightly connected groups. Each cluster is a topic area. Look at `dominant_category` |
| `bridges` | Nodes connecting clusters. These are the most valuable entries — they enable cross-domain reasoning |
| `structural_holes` | Pairs of clusters with no connections. These are blind spots |
| `degree_anomalies` | Nodes with suspicious degree patterns (isolated, under-linked, orphan hubs) |
| `top_betweenness` | Nodes that appear on the most shortest paths. If removed, the graph would fragment |

### Step 3 — Interpret for the Domain

This is where you (the LLM) add value. For each finding, answer: **what does this mean for the knowledge domain?**

Read representative entries from each cluster to understand what the cluster is *about*. The topology tells you the cluster exists; reading entries tells you *what it covers*.

For structural holes: are the two clusters *supposed* to be connected? (Quantum physics and medieval history probably aren't — but machine learning and neuroscience probably should be.)

For bridges: are these entries actually making meaningful cross-domain connections, or are they accidental connections (e.g. same person appears in two unrelated fields)?

For anomalies: is an "isolated" node really orphaned, or is it a newly-created entry that hasn't been linked yet?

### Step 4 — Recommend Actions

Based on interpretation, produce a prioritized action list. See [Action Patterns](#action-patterns) below.

### Step 5 — Log

Append to `log.md`:
```
YYYY-MM-DD topology | N nodes, M edges, C clusters, H holes, A anomalies → K actions proposed
```

## Interpreting Metrics

### Healthy KB Signals

- **Components = 1**: All knowledge is reachable from any entry
- **Reciprocity > 0.6**: Most links go both ways (good backlink hygiene)
- **Density 0.02–0.08**: Connected but not over-linked (every entry linking to every other is noise)
- **Clusters align with expected topic areas**: The detected communities match the real structure of the domain
- **Few degree anomalies**: Most nodes participate in the graph

### Warning Signs

- **Components > 1**: Knowledge islands. Urgent — these entries can't cross-reference each other
- **Reciprocity < 0.3**: Massive backlink debt. Run `kb:lint` first
- **Very high density (> 0.15)**: Over-linking — links become meaningless. Some entries may be linking to everything without real semantic connection
- **Single giant cluster**: No topic differentiation — entries aren't organized enough for the community detection to find structure. Consider whether wikilinks are too generic
- **Many degree anomalies**: Extraction quality issue — entities are mentioned but not elaborated

### Scale Expectations

| KB size | Expected clusters | Expected bridges | Acceptable holes |
|---------|-------------------|-----------------|-----------------|
| < 50 entries | 2-4 | 1-3 | 0-1 |
| 50-200 entries | 4-10 | 3-8 | 0-3 |
| 200-500 entries | 8-20 | 5-15 | 0-5 |
| 500+ entries | 15+ | 10+ | Depends on scope |

## Action Patterns

Each topology finding maps to a concrete action:

### Structural Hole → Source Acquisition or Cross-Linking

**If the clusters SHOULD be connected**: search the KB for entries that could plausibly link them. Run `related.py` with keywords from both clusters. If no natural connections exist, recommend a source that bridges the gap: "Adding a source on [topic that spans both clusters] would close this gap."

**If the clusters are correctly separate**: no action needed. Note in log that the hole was assessed and found intentional.

### Degree Anomaly → Entry Enrichment

**Isolated node**: Read it. Either (a) add links to related entries and add reciprocal links back, or (b) if it's genuinely unrelated to everything, question whether it belongs in this KB.

**Under-linked authority** (high in-degree, low out-degree): The entry is referenced everywhere but contains no outgoing links itself. Read it and add wikilinks to entities, topics, ideas it mentions. This is often a sign of a thin entity profile — consider `kb:revisit` on it.

**Orphan hub** (high out-degree, low in-degree): The entry links to many things but nothing links back. Usually a meta or source-analysis entry that was written but never cross-referenced from the entries it discusses.

### Bridge → Protection and Exploration

Bridge nodes are the most valuable entries. If a bridge has few sources (`source-ids` in frontmatter), it's a single point of failure — one disputed claim could break the cross-domain connection. Consider:
- Adding more sources that cover the same bridge topic
- Creating additional bridge entries that provide alternative connections
- Running `kb:iterate` focused on the bridge entry to deepen understanding

### Low Reciprocity → Backlink Sweep

If reciprocity < 0.5, the most impactful action is a bulk `kb:lint` run focused on missing backlinks. This is mechanical work, not analytical — but it dramatically improves graph quality.

## Self-Diagnosis

Topology analysis doubles as a **quality audit of the extraction process**. Patterns in the topology reveal systematic biases:

| Topology pattern | Extraction bias |
|-----------------|-----------------|
| Entity nodes mostly isolated | Entities extracted as stubs, not connected to ideas/topics |
| Citation cluster disconnected from knowledge | Citations created but not wikilinked to entity/topic/idea entries |
| Timeline entries in separate component | Dates extracted but not linked to events/entities they describe |
| Single massive cluster, no substructure | Over-linking — wikilinks added indiscriminately |
| Many clusters, almost no bridges | Under-linking between categories — entities don't link to ideas, topics don't mention people |

When a pattern repeats, update `.kb/rules.md` with a correction rule (propose to user first). This is rules co-evolution driven by data rather than anecdote.
